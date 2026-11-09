"""Minimal web app: audio page (2 upload slots, play/test/stop, live volume) and RTC setter."""

import logging
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, player, relay, rtc

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    for slot in ("playback", "test"):
        player.slot_dir(slot).mkdir(parents=True, exist_ok=True)
    relay.set_state(True)  # relay + playback audio both start as soon as the service does (at boot)
    player.play("playback")
    yield
    player.stop()
    relay.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return RedirectResponse("/audio")


@app.get("/audio")
def audio_page():
    return FileResponse(STATIC / "audio.html")


@app.get("/relay")
def relay_page():
    return FileResponse(STATIC / "relay.html")


@app.get("/rtc")
def rtc_page():
    return FileResponse(STATIC / "rtc.html")


@app.get("/reboot")
def reboot_page():
    return FileResponse(STATIC / "reboot.html")


@app.post("/api/reboot")
def reboot():
    # Delay so this HTTP response reaches the browser before the system goes down.
    subprocess.Popen(["sh", "-c", f"sleep 1; {config.REBOOT_CMD}"])
    return {"rebooting": True}


def status() -> dict:
    playback, test = player.current_file("playback"), player.current_file("test")
    return {
        "playback_file": playback.name if playback else None,
        "test_file": test.name if test else None,
        "playing": player.playing_slot(),  # "playback" | "test" | None
        "volume": player.load_config()["volume"],
        "relay": relay.is_on(),
        "system_time": rtc.system_time(),
        "rtc_time": rtc.rtc_time(),
    }


@app.get("/api/status")
def get_status():
    return status()


@app.post("/api/play")
def play():
    if player.play("playback") is None:
        raise HTTPException(400, "aucun son de lecture n'a été envoyé")
    return status()


@app.post("/api/play-test")
def play_test():
    if player.play("test") is None:
        raise HTTPException(400, "aucun son test n'a été envoyé")
    return status()


@app.post("/api/stop")
def stop():
    player.stop()
    return status()


class RelayState(BaseModel):
    on: bool


@app.post("/api/relay")
def set_relay(body: RelayState):
    relay.set_state(body.on)
    return {"relay": relay.is_on()}


class Volume(BaseModel):
    volume: int = Field(ge=0, le=100)
    persist: bool = True  # False while dragging the slider: live only, no disk write


@app.post("/api/volume")
def set_volume(body: Volume):
    player.set_volume(body.volume, body.persist)
    return {"volume": body.volume}


@app.post("/api/upload/{slot}")
async def upload(slot: str, request: Request, name: str):
    """Raw-body upload (no multipart dependency). The slot's previous file is deleted
    only once the new one has been fully received."""
    if slot not in ("playback", "test"):
        raise HTTPException(404, "emplacement inconnu")
    try:
        target = player.slot_dir(slot) / player.safe_name(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    tmp = target.with_name(target.name + ".part")
    size = 0
    try:
        with tmp.open("wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "fichier trop volumineux")
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "fichier vide")
        player.stop()  # also releases the old file if it was playing
        os.replace(tmp, target)  # atomic: mpv never sees a half-written file
        player.clear_slot(slot, keep=target)
        player.play(slot)  # every successful upload starts playing the new file
    finally:
        tmp.unlink(missing_ok=True)
    return status()


class SetTime(BaseModel):
    epoch: int  # UTC seconds, sent by the browser


@app.post("/api/rtc")
def set_rtc(body: SetTime):
    try:
        rtc.set_time(body.epoch)
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    return status()
