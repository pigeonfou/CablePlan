#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'sudo requis'; exit 1; }
install -d -m 0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' > /etc/apt/sources.list.d/cloudflared.list
apt-get update
apt-get install -y cloudflared
[[ ! -f /etc/systemd/system/cloudflared.service ]] || { echo 'Service existant conservé : ajoutez le hostname dans Cloudflare.'; exit 0; }
read -rsp 'Token du tunnel CablePlan (Cloudflare Zero Trust) : ' tunnel_token
printf '\n'
# cloudflared generates the service; token remains local, never in Git.
cloudflared service install "$tunnel_token"
unset tunnel_token
sed -i '/^CABLEPLAN_TUNNEL_CONFIGURED=/d' /etc/cableplan/cableplan.env
echo 'CABLEPLAN_TUNNEL_CONFIGURED=1' >> /etc/cableplan/cableplan.env
systemctl restart cableplan
