"""Minimal web app: upload the audio file mpv plays, set the RTC date."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import config, player, relay, rtc

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    relay.on()  # relay + audio both start as soon as the service does (at boot)
    player.play()
    yield
    player.stop()
    relay.off()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    f = player.current_file()
    return {"file": f.name if f else None, "playing": player.is_playing(), "system_time": rtc.system_time(), "rtc_time": rtc.rtc_time()}


@app.post("/api/upload")
async def upload(request: Request, name: str):
    """Raw-body upload (no multipart dependency): the file is the request body."""
    try:
        target = config.AUDIO_DIR / player.safe_name(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    tmp = target.with_name(target.name + ".part")
    size = 0
    try:
        with tmp.open("wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "file too large")
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "empty file")
        # Upload complete: only now touch the old file(s). A failed upload leaves them intact.
        player.stop()
        os.replace(tmp, target)  # atomic: mpv never sees a half-written file
        player.clear_audio_dir(keep=target)
    finally:
        tmp.unlink(missing_ok=True)
    return {"file": target.name, "playing": player.play() is not None}


class SetTime(BaseModel):
    epoch: int  # UTC seconds, sent by the browser


@app.post("/api/rtc")
def set_rtc(body: SetTime):
    try:
        rtc.set_time(body.epoch)
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    return status()
