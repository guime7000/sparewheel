"""All settings come from environment variables (see deploy/sparewheel.env)."""

import os
from pathlib import Path

AUDIO_DIR = Path(os.environ.get("SPAREWHEEL_AUDIO_DIR", "/home/ohm/OhmFiles/audio"))
RELAY_GPIO_PIN = int(os.environ.get("SPAREWHEEL_RELAY_PIN", "25"))  # BCM numbering
RELAY_ACTIVE_HIGH = os.environ.get("SPAREWHEEL_RELAY_ACTIVE_HIGH", "1") == "1"
LOOP = os.environ.get("SPAREWHEEL_LOOP", "1") == "1"
MPV_BIN = os.environ.get("SPAREWHEEL_MPV", "mpv")
MPV_EXTRA_ARGS = os.environ.get("SPAREWHEEL_MPV_ARGS", "").split()
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus"}
MAX_UPLOAD_BYTES = int(os.environ.get("SPAREWHEEL_MAX_UPLOAD_MB", "200")) * 1024 * 1024
