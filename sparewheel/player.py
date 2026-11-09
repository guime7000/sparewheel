"""Plays the newest file of AUDIO_DIR with mpv."""

import logging
import re
import subprocess
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)
_proc: subprocess.Popen | None = None


def safe_name(name: str) -> str:
    """Strip any path and odd characters; raise ValueError if not an allowed audio file."""
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).lstrip(".")
    if Path(base).suffix.lower() not in config.AUDIO_EXTENSIONS:
        raise ValueError(f"unsupported file type (allowed: {', '.join(sorted(config.AUDIO_EXTENSIONS))})")
    return base


def current_file() -> Path | None:
    files = [p for p in config.AUDIO_DIR.glob("*") if p.suffix.lower() in config.AUDIO_EXTENSIONS and p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def clear_audio_dir(keep: Path | None = None) -> None:
    """Delete every audio file (and leftover .part upload) from AUDIO_DIR, except `keep`."""
    for p in config.AUDIO_DIR.glob("*"):
        if p != keep and p.is_file() and (p.suffix.lower() in config.AUDIO_EXTENSIONS or p.suffix == ".part"):
            p.unlink()


def stop() -> None:
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None


def play() -> str | None:
    """(Re)start playback of the current file. Returns its name, or None if nothing to play."""
    stop()
    f = current_file()
    if f is None:
        logger.info("player: no audio file in %s", config.AUDIO_DIR)
        return None
    args = [config.MPV_BIN, "--no-video", "--no-terminal", *config.MPV_EXTRA_ARGS]
    if config.LOOP:
        args.append("--loop-file=inf")
    global _proc
    try:
        _proc = subprocess.Popen([*args, str(f)])
    except OSError:
        logger.exception("player: cannot start mpv")
        return None
    return f.name


def is_playing() -> bool:
    return _proc is not None and _proc.poll() is None
