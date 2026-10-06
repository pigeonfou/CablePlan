#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Exécuter avec sudo.'; exit 1; }
source /etc/os-release
[[ $ID == ubuntu && ( $VERSION_ID == 24.04 || $VERSION_ID == 26.04 ) ]] || { echo 'Ubuntu 24.04 / 26.04 requis.'; exit 1; }
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
lan_ip=${CABLEPLAN_LAN_IP:-}
if [[ -z $lan_ip ]]; then read -rp 'Adresse IPv4 LAN du serveur : ' lan_ip; fi
python3 - "$lan_ip" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1])
assert ip.version == 4 and ip.is_private and not ip.is_unspecified and not ip.is_loopback, 'Adresse IPv4 LAN privée requise'
PY
apt-get update
apt-get install -y git curl ca-certificates python3 python3-venv sqlite3 nginx build-essential sudo
id cableplan >/dev/null 2>&1 || useradd --system --home /var/lib/cableplan --shell /usr/sbin/nologin cableplan
id cableplan-runner >/dev/null 2>&1 || useradd --create-home --shell /bin/bash cableplan-runner
install -d -m 0755 /opt/cableplan /opt/cableplan/releases /usr/local/src
install -d -o cableplan -g cableplan -m 0700 /var/lib/cableplan
install -d -m 0700 /etc/cableplan /var/backups/cableplan
if [[ ! -f /etc/cableplan/cableplan.env ]]; then
    install -m 0600 /dev/null /etc/cableplan/cableplan.env
    echo 'CABLEPLAN_TUNNEL_CONFIGURED=' > /etc/cableplan/cableplan.env
fi
# Keep a root-owned Git mirror; the runner cannot modify privileged helper source.
if [[ ! -d /usr/local/src/cableplan.git ]]; then
    git init --bare /usr/local/src/cableplan.git
    git --git-dir=/usr/local/src/cableplan.git remote add origin https://github.com/pigeonfou/CablePlan.git
fi
sha=$(git -c safe.directory="$repo_dir" -C "$repo_dir" rev-parse HEAD)
release=/opt/cableplan/releases/$sha
if [[ ! -f $release/.installed ]]; then
    install -d -o cableplan -g cableplan -m 0755 "$release"
    git -c safe.directory="$repo_dir" -C "$repo_dir" archive "$sha" | tar -x -C "$release"
    chown -R cableplan:cableplan "$release"
    runuser -u cableplan -- python3 -m venv "$release/.venv"
    runuser -u cableplan -- "$release/.venv/bin/python" -m pip install "$release"
    touch "$release/.installed"
    chown -R root:root "$release"
    chmod -R a-w "$release"
fi
runuser -u cableplan -- env CABLEPLAN_DATA=/var/lib/cableplan "$release/.venv/bin/cableplan" migrate
ln -sfn "$release" /opt/cableplan/current
install -m 0644 "$repo_dir/packaging/systemd/cableplan.service" /etc/systemd/system/cableplan.service
if [[ ! -f /etc/nginx/sites-available/cableplan ]]; then
    sed "s/__LAN_IP__/$lan_ip/g" "$repo_dir/packaging/nginx/cableplan.conf" > /etc/nginx/sites-available/cableplan
fi
ln -sfn /etc/nginx/sites-available/cableplan /etc/nginx/sites-enabled/cableplan
# Disable stock default only when there are no other enabled sites.
if [[ -L /etc/nginx/sites-enabled/default ]] && ! find /etc/nginx/sites-enabled -mindepth 1 -maxdepth 1 ! -name default ! -name cableplan | read -r _; then
    rm /etc/nginx/sites-enabled/default
fi
# Ubuntu stock wildcard default listener can overlap this address. Leave an existing server untouched;
# on a fresh server the administrator can disable its default site if nginx -t reports a conflict.
for script in deploy rollback backup restore diagnose; do
    install -o root -g root -m 0755 "$repo_dir/scripts/$script.sh" "/usr/local/sbin/cableplan-$script"
done
cat > /etc/sudoers.d/cableplan-runner <<'SUDO'
cableplan-runner ALL=(root) NOPASSWD: /usr/local/sbin/cableplan-deploy
SUDO
chmod 0440 /etc/sudoers.d/cableplan-runner
visudo -cf /etc/sudoers.d/cableplan-runner
# Preserve local environment settings; update only deployed commit.
sed -i '/^CABLEPLAN_COMMIT=/d' /etc/cableplan/cableplan.env
echo "CABLEPLAN_COMMIT=$sha" >> /etc/cableplan/cableplan.env
nginx -t
systemctl daemon-reload
systemctl enable --now cableplan nginx
systemctl restart cableplan
systemctl reload nginx
for attempt in {1..20}; do
    if curl -fsS --unix-socket /run/cableplan/app.sock -H 'X-CablePlan-Access-Channel: lan' http://localhost/health; then
        echo; echo "Installation terminée. LAN : http://$lan_ip/"; exit 0
    fi
    sleep 1
done
echo 'Échec du health check : consultez journalctl -u cableplan.'; exit 1
