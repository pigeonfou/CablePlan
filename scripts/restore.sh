#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'sudo requis'; exit 1; }
exec 9>/run/lock/cableplan-deploy.lock
flock -n 9 || { echo "Opération en cours"; exit 1; }
[[ $# == 1 ]] || { echo 'Usage : cableplan-restore /var/backups/cableplan/<sauvegarde>'; exit 1; }
backup=$(realpath -e -- "$1")
[[ $backup == /var/backups/cableplan/* && -f $backup/database.sqlite && -f $backup/release ]] || exit 1
release=$(cat "$backup/release")
[[ $release =~ ^/opt/cableplan/releases/[0-9a-f]{40}$ && -x $release/.venv/bin/cableplan ]] || exit 1
python3 - "$backup/database.sqlite" <<'PY'
import sqlite3,sys
with sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True) as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
PY
systemctl stop cableplan
/usr/local/sbin/cableplan-backup >/dev/null
rm -f /var/lib/cableplan/database.sqlite-wal /var/lib/cableplan/database.sqlite-shm
install -o cableplan -g cableplan -m 0600 "$backup/database.sqlite" /var/lib/cableplan/database.sqlite
cp -a "$backup/config/." /etc/cableplan/
ln -sfn "$release" /opt/cableplan/current
systemctl start cableplan
for attempt in {1..20}; do
    if curl -fsS --unix-socket /run/cableplan/app.sock -H 'X-CablePlan-Access-Channel: lan' http://localhost/health; then echo; exit 0; fi
    sleep 1
done
exit 1
