#!/usr/bin/env bash
# PER-DEVICE setup for a clone of the sparewheel golden image: hostname + WiFi access point.
# Run on each cloned Pi:   sudo bash /opt/sparewheel/deploy/setup_host.sh
# Non-interactive (scripting 15 devices):
#   sudo DEVICE_HOSTNAME=sparewheel07 WIFI_PASSPHRASE=xxxxxxxx WIFI_COUNTRY=FR bash setup_host.sh
# The WiFi SSID is the hostname. Derived from Appestrio's Docs/Deployment/setup_host.sh, which found
# on real hardware that cloud-init rewrites /etc/hosts at every boot, that the Imager's WiFi client
# profile steals wlan0 from the AP, and that Android can't resolve <host>.local via mDNS.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)" >&2; exit 1; }

DEVICE_HOSTNAME="${DEVICE_HOSTNAME:-}"
WIFI_PASSPHRASE="${WIFI_PASSPHRASE:-}"
WIFI_COUNTRY="${WIFI_COUNTRY:-FR}"
INTERACTIVE=0

if [ -z "$DEVICE_HOSTNAME" ]; then
    read -rp "Device hostname (e.g. sparewheel1 ... sparewheel15): " DEVICE_HOSTNAME
    INTERACTIVE=1
fi
# RFC 1123 label: letters, digits, hyphens; max 32 chars (also the WiFi SSID limit).
if ! [[ "$DEVICE_HOSTNAME" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,30}[A-Za-z0-9])?$ ]]; then
    echo "ERROR: invalid hostname '$DEVICE_HOSTNAME' (letters, digits, '-', max 32 chars)." >&2
    exit 1
fi
if [ -z "$WIFI_PASSPHRASE" ]; then
    read -rsp "WiFi AP passphrase (8-63 chars): " WIFI_PASSPHRASE; echo
    INTERACTIVE=1
fi
if [ "${#WIFI_PASSPHRASE}" -lt 8 ] || [ "${#WIFI_PASSPHRASE}" -gt 63 ]; then
    echo "ERROR: WPA passphrase must be 8-63 characters." >&2
    exit 1
fi

if [ "$INTERACTIVE" = 1 ]; then
    echo
    echo "About to configure:  hostname = SSID = $DEVICE_HOSTNAME   (WiFi country $WIFI_COUNTRY)"
    read -rp "Continue? [y/N]: " CONFIRM
    case "$CONFIRM" in [yY]*) ;; *) echo "Aborted."; exit 1 ;; esac
fi

echo "--- Disabling cloud-init (it rewrites /etc/hosts and network config on every boot) ---"
if [ -d /etc/cloud ]; then
    touch /etc/cloud/cloud-init.disabled
    systemctl disable cloud-init cloud-init-local cloud-config cloud-final 2>/dev/null || true
else
    echo "No /etc/cloud, skipping."
fi

echo "--- Hostname ---"
hostnamectl set-hostname "$DEVICE_HOSTNAME"
# Replace (not append): this host must only know itself by its own hostname, never a stale alias.
if grep -q '^127\.0\.1\.1' /etc/hosts; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t${DEVICE_HOSTNAME}/" /etc/hosts
else
    printf '127.0.1.1\t%s\n' "$DEVICE_HOSTNAME" >> /etc/hosts
fi
hostname

echo "--- WiFi access point '$DEVICE_HOSTNAME' ---"
rfkill unblock wifi || true
iw reg set "$WIFI_COUNTRY" 2>/dev/null || true
CON_NAME="${DEVICE_HOSTNAME}-ap"
# Remove the golden image's / a previous run's AP profile(s) so only this one remains.
{ nmcli -t -f NAME connection show | grep -E -- '-ap$' || true; } | while IFS= read -r old; do
    nmcli connection delete "$old" || true
done
nmcli connection add type wifi ifname wlan0 con-name "$CON_NAME" autoconnect yes ssid "$DEVICE_HOSTNAME" \
    802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared \
    wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$WIFI_PASSPHRASE" \
    connection.autoconnect-priority 10

# Only one WiFi connection can hold the single onboard wlan0: disable autoconnect on every other one
# (e.g. the client profile from Raspberry Pi Imager) so the AP wins on every boot.
nmcli -t -f NAME,TYPE connection show \
  | awk -F: -v con="$CON_NAME" '($2=="802-11-wireless" || $2=="wifi") && $1!=con {print $1}' \
  | while IFS= read -r conn; do
        echo "  disabling autoconnect on '$conn'"
        nmcli connection modify "$conn" connection.autoconnect no
    done

# Android has no mDNS for ordinary apps, so answer plain DNS for <hostname>.local from the AP's dnsmasq.
# 10.42.0.1 is NetworkManager's fixed gateway for "shared" APs (same on every device: isolated networks).
mkdir -p /etc/NetworkManager/dnsmasq-shared.d
echo "address=/${DEVICE_HOSTNAME}.local/10.42.0.1" > /etc/NetworkManager/dnsmasq-shared.d/sparewheel.conf

echo "WARNING: if you are connected over WiFi, bringing the AP up drops this session."
nmcli connection down "$CON_NAME" 2>/dev/null || true
nmcli connection up "$CON_NAME"

echo
echo "=== Done: SSID '$DEVICE_HOSTNAME' -> http://$DEVICE_HOSTNAME.local/  (or http://10.42.0.1/) ==="
echo "Reboot to confirm everything comes up on its own:  sudo reboot"
