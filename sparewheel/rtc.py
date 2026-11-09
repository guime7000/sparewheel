"""Read / set the system clock and the hardware RTC (needs root)."""

import subprocess
from datetime import datetime, timezone


def _run(*cmd: str) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def system_time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rtc_time() -> str | None:
    try:
        return _run("hwclock", "--utc", "-r")
    except Exception:
        return None


def set_time(epoch: int) -> None:
    """Set system clock from a UTC epoch, then write it to the RTC."""
    if not 946684800 <= epoch <= 4102444800:  # 2000..2100
        raise ValueError("date hors limites (2000 à 2100)")
    _run("date", "-u", "-s", f"@{epoch}")
    _run("hwclock", "--utc", "--systohc")
