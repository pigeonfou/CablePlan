#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'sudo requis'; exit 1; }
[[ ${1:-} =~ ^[0-9a-f]{40}$ ]] || { echo 'SHA Git complet requis'; exit 1; }
exec 9>/run/lock/cableplan-deploy.lock
flock -n 9 || { echo 'Un déploiement est déjà en cours'; exit 1; }
sha=$1
mirror=/usr/local/src/cableplan.git
git --git-dir="$mirror" -c core.hooksPath=/dev/null fetch origin refs/heads/main:refs/heads/main
[[ $(git --git-dir="$mirror" rev-parse refs/heads/main) == "$sha" ]] || { echo 'Commit obsolète ou hors main : ignoré'; exit 1; }
release=/opt/cableplan/releases/$sha
if [[ ! -f $release/.installed ]]; then
    install -d -o cableplan -g cableplan -m 0755 "$release"
    git --git-dir="$mirror" archive "$sha" | tar -x -C "$release"
    chown -R cableplan:cableplan "$release"
    runuser -u cableplan -- python3 -m venv "$release/.venv"
    runuser -u cableplan -- "$release/.venv/bin/python" -m pip install "$release"
    touch "$release/.installed"
    chown -R root:root "$release"
    chmod -R a-w "$release"
fi
systemctl stop cableplan
if ! backup=$(/usr/local/sbin/cableplan-backup); then
    systemctl start cableplan
    exit 1
fi
previous=$(cat "$backup/release")
rollback_on_error(){
    trap - ERR
    echo 'Échec : restauration automatique du code et de la base.'
    systemctl stop cableplan || true
    rm -f /var/lib/cableplan/database.sqlite-wal /var/lib/cableplan/database.sqlite-shm
    install -o cableplan -g cableplan -m 0600 "$backup/database.sqlite" /var/lib/cableplan/database.sqlite
    cp -a "$backup/config/." /etc/cableplan/
    ln -sfn "$previous" /opt/cableplan/current
    systemctl start cableplan
    for attempt in {1..20}; do
        if curl -fsS --unix-socket /run/cableplan/app.sock -H "X-CablePlan-Access-Channel: lan" http://localhost/health; then break; fi
        sleep 1
    done
    exit 1
}
trap rollback_on_error ERR
runuser -u cableplan -- env CABLEPLAN_DATA=/var/lib/cableplan "$release/.venv/bin/cableplan" migrate
ln -sfn "$release" /opt/cableplan/current
sed -i '/^CABLEPLAN_COMMIT=/d' /etc/cableplan/cableplan.env
echo "CABLEPLAN_COMMIT=$sha" >> /etc/cableplan/cableplan.env
systemctl start cableplan
healthy=false
for attempt in {1..30}; do
    if curl -fsS --unix-socket /run/cableplan/app.sock -H 'X-CablePlan-Access-Channel: lan' http://localhost/health; then healthy=true; break; fi
    sleep 1
done
[[ $healthy == true ]]
trap - ERR
echo; echo "Commit $sha déployé. Sauvegarde : $backup"
