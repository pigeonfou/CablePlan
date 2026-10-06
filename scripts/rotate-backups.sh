#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || exit 1
# Keep at least 10 backups, and all backups less than 30 days old.
mapfile -t entries < <(find /var/backups/cableplan -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -r)
for ((i=10; i<${#entries[@]}; i++)); do
    backup=/var/backups/cableplan/${entries[$i]}
    [[ ${entries[$i]} =~ ^[0-9]{8}T[0-9]{6}-[0-9a-f]{8}$ ]] || continue
    if [[ -n $(find "$backup" -maxdepth 0 -mtime +30 -print) ]]; then
        printf 'Rotation sauvegarde : %s\n' "${entries[$i]}"
        rm -rf -- "$backup"
    fi
done
