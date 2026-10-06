#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'sudo requis'; exit 1; }
backup_dir=/var/backups/cableplan/$(date -u +%Y%m%dT%H%M%S)-$(python3 -c 'import secrets; print(secrets.token_hex(4))')
install -d -m 0700 "$backup_dir"
python3 - "$backup_dir/database.sqlite" <<'PY'
import sqlite3,sys
with sqlite3.connect('file:/var/lib/cableplan/database.sqlite?mode=ro',uri=True) as source, sqlite3.connect(sys.argv[1]) as dest:
    source.backup(dest)
    assert dest.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
PY
cp -a /etc/cableplan "$backup_dir/config"
readlink -f /opt/cableplan/current > "$backup_dir/release"
echo "$backup_dir"
# Backups are not deleted automatically. Schedule a reviewed retention policy after first production validation.
