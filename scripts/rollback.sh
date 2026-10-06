#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || exit 1
latest=$(find /var/backups/cableplan -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | tail -1)
[[ -n $latest ]] || { echo 'Aucune sauvegarde'; exit 1; }
exec /usr/local/sbin/cableplan-restore "/var/backups/cableplan/$latest"
