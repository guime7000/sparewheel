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

## Deploying a fleet (golden image, same approach as Appestrio)

**1. Build the golden Pi once** (internet needed; user `ohm` must exist):

    sudo ./deploy/setup.sh          # mpv + service + RTC overlay; no hostname, no AP
    sudo reboot                     # check the service runs, then clone the SD card

**2. On each clone** (15 of them), set hostname + WiFi access point. The SSID is the hostname:

    sudo bash /opt/sparewheel/deploy/setup_host.sh                       # interactive
    sudo DEVICE_HOSTNAME=sparewheel07 WIFI_PASSPHRASE=<8+ chars> bash /opt/sparewheel/deploy/setup_host.sh   # scripted

`setup_host.sh` sets the hostname and `/etc/hosts`, disables cloud-init, creates the NetworkManager hotspot (Pi at `10.42.0.1`),
disables autoconnect on any other WiFi profile (e.g. the Imager's) so the AP always wins `wlan0`, and adds a plain-DNS entry so
`http://<hostname>.local/` also resolves on Android. Then `sudo reboot`, join the WiFi and open `http://<hostname>.local/`.
Over WiFi, the script drops your SSH session when the AP comes up: use Ethernet or run it from the console.

The app runs as the systemd unit `sparewheel.service`, enabled at boot by `setup.sh` (`systemctl enable`): at each power-on it
switches the relay on, starts mpv and serves the web app. Check with `systemctl status sparewheel` / `journalctl -u sparewheel`.

### Ready-to-flash images (nothing to run on site)

Instead of running `setup_host.sh` on each Pi, build the 15 images on your laptop from the golden image. Each one already has
its hostname, WiFi access point (SSID = hostname), DNS entry and cloud-init disabled:

    # 1. golden card: finish setup.sh + update.sh, remove the Imager WiFi profile, shut down
    # 2. golden_image.img = dd + PiShrink of that card (see Appestrio's golden_image_plan.md)
    # 3. on the laptop:
    sudo ./deploy/make_images.sh golden_image.img out lumestrio 1 16      # asks the fleet passphrase
    xz -9 -T0 out/*.img && sha256sum out/*.xz > out/SHA256SUMS            # optional, for transport

This produces `out/lumestrio1.img` ... `lumestrio16.img`. Flash each one (Raspberry Pi Imager "Use custom"), power on, join
the SSID `lumestrio7` and open `http://lumestrio7.local/`. The script refuses to build if the golden image still contains a
WiFi client profile (so no home WiFi password ships). Try `... lumestrio 1 1` first and check the result before building all 15.

**Updating a Pi after changing the code:** `sudo ./deploy/update.sh` from the repo (the service runs the copy installed in
`/opt/sparewheel/venv`, not the repo files, so a plain `cp` is not enough).

Settings (relay pin/polarity, mpv args, reboot command): `/etc/sparewheel.env`.

## Dev

    pip install -e '.[dev]' && pytest
    SPAREWHEEL_AUDIO_DIR=/tmp/audio uvicorn sparewheel.web:app --port 8000   # relay/RTC just log errors off-Pi

## Notes / caveats

- Service runs as root (needs `hwclock`, `date -s`, port 80). The AP is the only access path; use a real WPA password. No auth on the page.
- The RTC is written via `date -u -s` + `hwclock --systohc`; the time sent is the browser's UTC epoch. Wiring: DS3231 SDA/SCL on GPIO2/3, 3.3V.
- Relay polarity: set `SPAREWHEEL_RELAY_ACTIVE_HIGH=0` for active-low boards.
- Untested on hardware so far.
