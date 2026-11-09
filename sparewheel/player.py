"""mpv playback of the two audio slots, controlled live over mpv's JSON IPC socket.

Slots: "playback" = AUDIO_DIR/playback (played at boot), "test" = AUDIO_DIR/test
(calibration sample). Each slot holds one file; the volume lives in MPV_CONFIG = AUDIO_DIR/mpv_config.json and is
passed to mpv at every launch. mpv is always started looping.
"""

import json
import logging
import re
import socket
import subprocess
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)
_proc: subprocess.Popen | None = None
_playing_slot: str | None = None


# ---------- files ----------

def safe_name(name: str) -> str:
    """Strip any path and odd characters; raise ValueError if not an allowed audio file."""
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).lstrip(".")
    if Path(base).suffix.lower() not in config.AUDIO_EXTENSIONS:
        raise ValueError(f"type de fichier non pris en charge (autorisés : {', '.join(sorted(config.AUDIO_EXTENSIONS))})")
    return base


def slot_dir(slot: str) -> Path:
    if slot == "playback":
        return config.AUDIO_DIR / "playback"
    if slot == "test":
        return config.AUDIO_DIR / "test"
    raise ValueError(f"unknown slot {slot!r}")


def current_file(slot: str = "playback") -> Path | None:
    files = [p for p in slot_dir(slot).glob("*") if p.suffix.lower() in config.AUDIO_EXTENSIONS and p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def clear_slot(slot: str, keep: Path | None = None) -> None:
    """Delete every audio file (and leftover .part upload) of the slot, except `keep`."""
    for p in slot_dir(slot).glob("*"):
        if p != keep and p.is_file() and (p.suffix.lower() in config.AUDIO_EXTENSIONS or p.suffix == ".part"):
            p.unlink()


# ---------- JSON config (volume) ----------

def load_config() -> dict:
    try:
        volume = int(json.loads(config.MPV_CONFIG.read_text())["volume"])
    except (OSError, ValueError, KeyError, TypeError):
        volume = config.DEFAULT_VOLUME
    return {"volume": max(0, min(100, volume))}


def save_config(volume: int) -> None:
    config.MPV_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.MPV_CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps({"volume": volume}))
    tmp.replace(config.MPV_CONFIG)


# ---------- mpv ----------

def _force_alsa_mixer_to_max() -> None:
    """Hardware mixer at 100% so mpv's volume is the single loudness knob (best effort)."""
    for control in ("Master", "PCM", "Headphone", "Speaker"):
        try:
            subprocess.run(["amixer", "sset", control, "100%", "unmute"], capture_output=True, timeout=2)
        except (OSError, subprocess.SubprocessError):
            pass


def playing_slot() -> str | None:
    return _playing_slot if _proc is not None and _proc.poll() is None else None


def stop() -> None:
    global _proc, _playing_slot
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = _playing_slot = None


def play(slot: str = "playback") -> str | None:
    """(Re)start mpv on the slot's file, looping, at the saved volume. Returns the file name or None."""
    global _proc, _playing_slot
    stop()
    f = current_file(slot)
    if f is None:
        logger.info("player: no audio file in slot %s", slot)
        return None
    _force_alsa_mixer_to_max()
    args = [
        config.MPV_BIN, "--no-video", "--no-terminal",
        f"--volume={load_config()['volume']}",
        "--loop-file=inf",  # always loop
        f"--input-ipc-server={config.MPV_IPC_SOCKET}",
        *config.MPV_EXTRA_ARGS, str(f),
    ]
    try:
        _proc = subprocess.Popen(args)
    except OSError:
        logger.exception("player: cannot start mpv")
        return None
    _playing_slot = slot
    return f.name


def _ipc(command: list) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        s.connect(config.MPV_IPC_SOCKET)
        s.sendall(json.dumps({"command": command}).encode() + b"\n")


def set_volume(volume: int, persist: bool) -> None:
    """Apply `volume` (0-100) to the running mpv right now; optionally save it for next launches."""
    if persist:
        save_config(volume)
    if playing_slot():
        try:
            _ipc(["set_property", "volume", volume])
        except OSError:
            logger.warning("player: cannot reach mpv IPC socket to change volume live")
