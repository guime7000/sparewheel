# sparewheel

Light Raspberry Pi 4 box derived from the useful bits of Appestrio (paused):

- Pi is a **WiFi access point** (NetworkManager hotspot, Pi at `10.42.0.1`)
- at boot a **GPIO relay** is switched on (default BCM 25, same as Appestrio)
- at boot **mpv** plays the newest file of `/home/ohm/OhmFiles/audio` (looped)
- a minimal **web page** uploads that file (restarts playback) and **sets the date** on an I2C **RTC** module (DS3231 by default)

All of it is one small FastAPI service (`sparewheel/`) run by systemd; no DB, no build step.

## Install (on the Pi, as root)

    AP_SSID=sparewheel AP_PASSWORD=<8+ chars> RTC_MODEL=ds3231 ./deploy/setup.sh && reboot

Then join the WiFi and open http://10.42.0.1/. Settings (relay pin/polarity, loop, mpv args): `/etc/sparewheel.env`.

## Dev

    pip install -e '.[dev]' && pytest
    SPAREWHEEL_AUDIO_DIR=/tmp/audio uvicorn sparewheel.web:app --port 8000   # relay/RTC just log errors off-Pi

## Notes / caveats

- Service runs as root (needs `hwclock`, `date -s`, port 80). The AP is the only access path; use a real WPA password. No auth on the page.
- The RTC is written via `date -u -s` + `hwclock --systohc`; the time sent is the browser's UTC epoch. Wiring: DS3231 SDA/SCL on GPIO2/3, 3.3V.
- Relay polarity: set `SPAREWHEEL_RELAY_ACTIVE_HIGH=0` for active-low boards.
- Untested on hardware so far.
