#!/usr/bin/env bash
set -uo pipefail
. /etc/os-release
printf 'OS : %s\n' "$PRETTY_NAME"
python3 --version
df -h /var/lib/cableplan
systemctl is-active cableplan nginx cloudflared
curl -fsS --unix-socket /run/cableplan/app.sock -H 'X-CablePlan-Access-Channel: lan' http://localhost/health
printf '\n'
sudo -u cableplan env CABLEPLAN_DATA=/var/lib/cableplan /opt/cableplan/current/.venv/bin/cableplan diagnose
