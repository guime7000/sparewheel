"""All settings come from environment variables (see deploy/sparewheel.env)."""

import os
from pathlib import Path

AUDIO_DIR = Path(os.environ.get("SPAREWHEEL_AUDIO_DIR", "/home/ohm/OhmFiles/audio"))  # AUDIO_DIR/playback and AUDIO_DIR/test
# JSON settings (volume) read at every mpv launch -- i.e. at each reboot.
MPV_CONFIG = Path(os.environ.get("SPAREWHEEL_MPV_CONFIG", str(AUDIO_DIR / "mpv_config.json")))
MPV_IPC_SOCKET = os.environ.get("SPAREWHEEL_MPV_SOCKET", "/tmp/sparewheel-mpv.sock")
RELAY_GPIO_PIN = int(os.environ.get("SPAREWHEEL_RELAY_PIN", "25"))  # BCM numbering
RELAY_ACTIVE_HIGH = os.environ.get("SPAREWHEEL_RELAY_ACTIVE_HIGH", "1") == "1"
MPV_BIN = os.environ.get("SPAREWHEEL_MPV", "mpv")
MPV_EXTRA_ARGS = os.environ.get("SPAREWHEEL_MPV_ARGS", "").split()
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus"}
MAX_UPLOAD_BYTES = int(os.environ.get("SPAREWHEEL_MAX_UPLOAD_MB", "200")) * 1024 * 1024
DEFAULT_VOLUME = 100
# Command run by the Reboot page. Override in dev (e.g. "echo reboot") so a laptop is never rebooted by accident.
REBOOT_CMD = os.environ.get("SPAREWHEEL_REBOOT_CMD", "systemctl reboot")
