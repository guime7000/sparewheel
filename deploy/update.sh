#!/usr/bin/env bash
# Deploy the current repo checkout to THIS Pi and restart the service. Run as root from the repo root:
#   sudo ./deploy/update.sh
# The service runs the copy pip installed in /opt/sparewheel/venv, NOT the repo files, so copying
# files into /opt/sparewheel is not enough: the package must be reinstalled.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
SRC="$(cd "$(dirname "$0")/.." && pwd)"

rm -rf /opt/sparewheel/sparewheel /opt/sparewheel/deploy
cp -r "$SRC/sparewheel" "$SRC/deploy" "$SRC/pyproject.toml" /opt/sparewheel/
/opt/sparewheel/venv/bin/pip install --force-reinstall --no-deps /opt/sparewheel
cp "$SRC/deploy/sparewheel.service" /etc/systemd/system/
systemctl daemon-reload
systemctl restart sparewheel
sleep 2
echo "sparewheel: $(systemctl is-active sparewheel)"
echo "installed audio.html has refresh() call: $(grep -c '^refresh();' /opt/sparewheel/venv/lib/python3*/site-packages/sparewheel/static/audio.html)"
echo "(/etc/sparewheel.env is left untouched; hard-refresh the browser with Ctrl+Shift+R)"
