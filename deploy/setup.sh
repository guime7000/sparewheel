#!/usr/bin/env bash
# GOLDEN IMAGE setup (run once, as root, from the repo root, on the Pi that will be cloned).
# Installs mpv + the sparewheel service + the RTC overlay. Does NOT touch hostname or WiFi AP:
# that is per-device and done on each clone by deploy/setup_host.sh.
# Optional env: RTC_MODEL (ds3231|ds1307|pcf8523, "" = skip)
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }

RTC_MODEL="${RTC_MODEL-ds3231}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

apt-get update
apt-get install -y mpv python3-venv python3-lgpio i2c-tools
# hwclock lives in util-linux-extra on Debian 13 (Trixie); absent/irrelevant on older releases
apt-get install -y util-linux-extra 2>/dev/null || true

# --- app ---
mkdir -p /opt/sparewheel /home/ohm/OhmFiles/audio/playback /home/ohm/OhmFiles/audio/test
chown -R ohm:ohm /home/ohm/OhmFiles  # user "ohm" must exist
cp -r "$SRC/sparewheel" "$SRC/deploy" "$SRC/pyproject.toml" /opt/sparewheel/
python3 -m venv --system-site-packages /opt/sparewheel/venv
/opt/sparewheel/venv/bin/pip install /opt/sparewheel
[ -f /etc/sparewheel.env ] || cp "$SRC/deploy/sparewheel.env" /etc/sparewheel.env
cp "$SRC/deploy/sparewheel.service" /etc/systemd/system/
# Start the service at every boot (relay on + mpv playback + web app), and now:
systemctl daemon-reload && systemctl enable --now sparewheel

# --- RTC on I2C ---
if [ -n "$RTC_MODEL" ]; then
  CFG=/boot/firmware/config.txt
  grep -q '^dtparam=i2c_arm=on' $CFG || echo 'dtparam=i2c_arm=on' >> $CFG
  grep -q '^dtoverlay=i2c-rtc' $CFG || echo "dtoverlay=i2c-rtc,$RTC_MODEL" >> $CFG
  apt-get remove -y fake-hwclock 2>/dev/null || true
  systemctl disable --now fake-hwclock 2>/dev/null || true
fi

echo "sparewheel.service: enabled=$(systemctl is-enabled sparewheel), now=$(systemctl is-active sparewheel)"
echo "Golden image ready. Reboot, check the service, then clone the SD card."
echo "On each clone, run: sudo bash /opt/sparewheel/deploy/setup_host.sh"
