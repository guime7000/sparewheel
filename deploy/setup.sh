#!/usr/bin/env bash
# One-shot install for Raspberry Pi OS (Bookworm/Trixie, NetworkManager). Run as root from the repo root.
# Optional env: AP_SSID AP_PASSWORD (>=8 chars) RTC_MODEL (ds3231|ds1307|pcf8523, "" = skip) WIFI_COUNTRY
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }

AP_SSID="${AP_SSID:-sparewheel}"
AP_PASSWORD="${AP_PASSWORD:-changeme123}"
RTC_MODEL="${RTC_MODEL-ds3231}"
WIFI_COUNTRY="${WIFI_COUNTRY:-FR}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

apt-get update
apt-get install -y mpv python3-venv python3-lgpio i2c-tools

# --- app ---
mkdir -p /opt/sparewheel /home/ohm/OhmFiles/audio/playback /home/ohm/OhmFiles/audio/test
chown -R ohm:ohm /home/ohm/OhmFiles  # user "ohm" must exist
cp -r "$SRC/sparewheel" "$SRC/pyproject.toml" /opt/sparewheel/
python3 -m venv --system-site-packages /opt/sparewheel/venv
/opt/sparewheel/venv/bin/pip install /opt/sparewheel
[ -f /etc/sparewheel.env ] || cp "$SRC/deploy/sparewheel.env" /etc/sparewheel.env
cp "$SRC/deploy/sparewheel.service" /etc/systemd/system/
systemctl daemon-reload && systemctl enable sparewheel

# --- WiFi access point (NetworkManager "shared" mode = built-in DHCP; Pi is 10.42.0.1) ---
rfkill unblock wifi || true
iw reg set "$WIFI_COUNTRY" || true
nmcli connection delete sparewheel-ap 2>/dev/null || true
nmcli connection add type wifi ifname wlan0 con-name sparewheel-ap autoconnect yes ssid "$AP_SSID" \
  802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$AP_PASSWORD"

# --- RTC on I2C ---
if [ -n "$RTC_MODEL" ]; then
  CFG=/boot/firmware/config.txt
  grep -q '^dtparam=i2c_arm=on' $CFG || echo 'dtparam=i2c_arm=on' >> $CFG
  grep -q '^dtoverlay=i2c-rtc' $CFG || echo "dtoverlay=i2c-rtc,$RTC_MODEL" >> $CFG
  apt-get remove -y fake-hwclock 2>/dev/null || true
  systemctl disable --now fake-hwclock 2>/dev/null || true
fi

echo "Done. Reboot. Then join WiFi '$AP_SSID' and open http://10.42.0.1/"
