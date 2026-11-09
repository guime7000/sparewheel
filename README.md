# sparewheel

Light Raspberry Pi 4 box derived from the useful bits of Appestrio (paused):

- Pi is a **WiFi access point** (NetworkManager hotspot, Pi at `10.42.0.1`)
- at boot a **GPIO relay** is switched on (default BCM 25, same as Appestrio)
- at boot **mpv** plays the file of `/home/ohm/OhmFiles/audio/playback`, always looping, at the saved volume
- a minimal **web app** in French with four pages (menu at the top; `/` redirects to `/audio`). **`/audio`**, modelled on Appestrio's Audio page:
  - two upload forms: **playback sound** (`audio/playback/`) and **test sound** (`audio/test/`); a new upload replaces the slot's previous file once fully received, then starts playing it
  - **Play / Test sound / Stop** buttons
  - a **volume slider** that acts on mpv live through its JSON IPC socket (`/tmp/sparewheel-mpv.sock`); the value is saved when you release it
- **`/rtc`**: shows system and RTC time, **sets the date** on an I2C **RTC** module (DS3231 by default)
- **`/relay`**: "Test relais" page with *Allumer* / *Éteindre* buttons (the relay is on after boot, so *Allumer* starts greyed)
- **`/reboot`**: one button; a confirmation dialog, then `systemctl reboot`

The volume is saved when the slider is released, in `/home/ohm/OhmFiles/audio/mpv_config.json` (`{"volume": 80}`). mpv has no JSON config format, so the service reads this file at every mpv launch (so at each reboot) and passes it as `--volume`. There is no loop setting: mpv always runs with `--loop-file=inf`.

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
