#!/usr/bin/env bash
# Build N ready-to-flash per-device images from the golden image, ON YOUR LAPTOP (no Pi needed).
# Each image gets its own hostname, WiFi access point (SSID = hostname) and DNS entry, written
# straight into the image's filesystem: the offline equivalent of deploy/setup_host.sh.
#
#   sudo ./deploy/make_images.sh golden_image.img out_dir lumestrio 1 16
#     -> out_dir/lumestrio1.img ... lumestrio16.img   (names = prefix + number, no zero-padding)
#
# Env: WIFI_PASSPHRASE (8-63 chars, asked silently if unset; same for the whole fleet)
#      WIFI_COUNTRY (default FR; written to cmdline.txt so the AP is allowed at boot)
# The golden image must be the one made BEFORE setup_host.sh, shrunk with PiShrink, with no WiFi
# client profile left in it (this script refuses to continue if it finds one).
set -euo pipefail

valid_name() { [[ "$1" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,30}[A-Za-z0-9])?$ ]]; }

# customize_root ROOTFS BOOTFS NAME PASSPHRASE COUNTRY
# Pure file edits (no mounting): testable against a fake directory tree.
customize_root() {
    local root="$1" boot="$2" name="$3" pass="$4" country="$5"
    local old=""
    [ -f "$root/etc/hostname" ] && old="$(tr -d '[:space:]' < "$root/etc/hostname")"

    # Refuse to ship someone's WiFi password: any leftover client profile is an error.
    local nm="$root/etc/NetworkManager/system-connections" f
    if [ -d "$nm" ]; then
        for f in "$nm"/*; do
            [ -e "$f" ] || continue
            if grep -q -E '^type=wifi' "$f" && ! grep -q -E '^mode=ap' "$f"; then
                echo "ERROR: golden image still has a WiFi client profile: ${f#"$root"} -- remove it first." >&2
                return 1
            fi
        done
    fi
    if [ -d "$root/etc/netplan" ] && grep -rIl -E 'wifis:|access-points:' "$root/etc/netplan" 2>/dev/null | grep -q .; then
        echo "ERROR: golden image still has a netplan WiFi config in /etc/netplan -- remove it first." >&2
        return 1
    fi

    # Hostname + /etc/hosts (replace the 127.0.1.1 line; then any other alias of the old name).
    echo "$name" > "$root/etc/hostname"
    touch "$root/etc/hosts"
    if grep -q '^127\.0\.1\.1' "$root/etc/hosts"; then
        sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t${name}/" "$root/etc/hosts"
    else
        printf '127.0.1.1\t%s\n' "$name" >> "$root/etc/hosts"
    fi
    if [ -n "$old" ] && [ "$old" != "$name" ] && [[ "$old" =~ ^[A-Za-z0-9.-]+$ ]]; then
        sed -i "s/\b${old//./\\.}\b/${name}/g" "$root/etc/hosts"
    fi

    # cloud-init would rewrite /etc/hosts / hostname at boot.
    if [ -d "$root/etc/cloud" ]; then touch "$root/etc/cloud/cloud-init.disabled"; fi

    # The access point, as a NetworkManager keyfile (what `nmcli connection add ... ipv4.method shared` writes).
    mkdir -p "$nm"
    find "$nm" -maxdepth 1 -name '*-ap.nmconnection' -delete
    local uuid; uuid="$(cat /proc/sys/kernel/random/uuid)"
    cat > "$nm/${name}-ap.nmconnection" <<EOC
[connection]
id=${name}-ap
uuid=${uuid}
type=wifi
interface-name=wlan0
autoconnect=true
autoconnect-priority=10

[wifi]
mode=ap
ssid=${name}
band=bg

[wifi-security]
key-mgmt=wpa-psk
psk=${pass}

[ipv4]
method=shared

[ipv6]
method=ignore
EOC
    chmod 600 "$nm/${name}-ap.nmconnection"; chown 0:0 "$nm/${name}-ap.nmconnection" 2>/dev/null || true

    # Plain-DNS entry for Android (<name>.local); drop stale ones for the old name.
    local dns="$root/etc/NetworkManager/dnsmasq-shared.d"
    mkdir -p "$dns"
    if [ -n "$old" ] && [ "$old" != "$name" ]; then
        { grep -l -F -- "${old}.local" "$dns"/* 2>/dev/null || true; } | while IFS= read -r f; do rm -f -- "$f"; done
    fi
    echo "address=/${name}.local/10.42.0.1" > "$dns/sparewheel.conf"

    # Regulatory domain on the kernel command line (single line), so the AP is allowed from first boot.
    if [ -f "$boot/cmdline.txt" ] && ! grep -q 'ieee80211_regdom=' "$boot/cmdline.txt"; then
        sed -i "1s/\$/ cfg80211.ieee80211_regdom=${country}/" "$boot/cmdline.txt"
    fi
}

main() {
    [ "$(id -u)" = 0 ] || { echo "run as root (sudo)" >&2; exit 1; }
    [ "$#" -eq 5 ] || { sed -n '2,10p' "$0" >&2; exit 1; }
    local golden="$1" outdir="$2" prefix="$3" first="$4" last="$5"
    local country="${WIFI_COUNTRY:-FR}" pass="${WIFI_PASSPHRASE:-}"
    [ -f "$golden" ] || { echo "ERROR: $golden not found" >&2; exit 1; }
    [[ "$first" =~ ^[0-9]+$ && "$last" =~ ^[0-9]+$ ]] && [ "$first" -le "$last" ] \
        || { echo "ERROR: first and last must be numbers with first <= last" >&2; exit 1; }
    if [ -z "$pass" ]; then read -rsp "Fleet WiFi passphrase (8-63 chars): " pass; echo; fi
    if [ "${#pass}" -lt 8 ] || [ "${#pass}" -gt 63 ]; then echo "ERROR: passphrase must be 8-63 chars" >&2; exit 1; fi
    mkdir -p "$outdir"

    local i name img loopdev mnt
    for ((i = first; i <= last; i++)); do
        name="${prefix}${i}"
        valid_name "$name" || { echo "ERROR: invalid hostname '$name'" >&2; exit 1; }
        img="$outdir/$name.img"
        [ ! -e "$img" ] || { echo "ERROR: $img already exists, not overwriting" >&2; exit 1; }
    done

    for ((i = first; i <= last; i++)); do
        name="${prefix}${i}"; img="$outdir/$name.img"
        echo "=== $name ==="
        cp --sparse=always "$golden" "$img"
        loopdev="$(losetup --find --show --partscan "$img")"
        mnt="$(mktemp -d)"
        cleanup() { umount "$mnt/boot/firmware" 2>/dev/null || true; umount "$mnt" 2>/dev/null || true; losetup -d "$loopdev" 2>/dev/null || true; rmdir "$mnt" 2>/dev/null || true; }
        trap cleanup EXIT
        mount "${loopdev}p2" "$mnt"
        mkdir -p "$mnt/boot/firmware"; mount "${loopdev}p1" "$mnt/boot/firmware"
        if ! customize_root "$mnt" "$mnt/boot/firmware" "$name" "$pass" "$country"; then
            cleanup; trap - EXIT; rm -f "$img"; exit 1
        fi
        sync; cleanup; trap - EXIT
        echo "  -> $img"
    done
    echo
    echo "Done: $((last - first + 1)) images in $outdir. Compress/verify if you like:  xz -9 -T0 $outdir/*.img ; sha256sum $outdir/*"
}

if [ "${BASH_SOURCE[0]:-$0}" = "$0" ]; then main "$@"; fi
