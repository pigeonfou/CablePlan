#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'sudo requis'; exit 1; }
install -d -m 0700 /etc/cableplan/git
key=/etc/cableplan/git/deploy-ed25519
[[ -f $key ]] || ssh-keygen -q -t ed25519 -N '' -C cableplan-readonly-deploy -f "$key"
# Verify the server host key against GitHub's published Ed25519 fingerprint.
known=$(mktemp)
trap 'rm -f "$known"' EXIT
ssh-keyscan -p 443 -t ed25519 ssh.github.com 2>/dev/null > "$known"
[[ $(ssh-keygen -lf "$known" -E sha256 | awk '{print $2}') == 'SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU' ]] || { echo 'Empreinte SSH GitHub inattendue'; exit 1; }
install -m 0600 "$known" /etc/cableplan/git/known_hosts
git --git-dir=/usr/local/src/cableplan.git remote set-url origin ssh://git@ssh.github.com:443/pigeonfou/CablePlan.git
git --git-dir=/usr/local/src/cableplan.git config core.sshCommand 'ssh -i /etc/cableplan/git/deploy-ed25519 -o IdentitiesOnly=yes -o UserKnownHostsFile=/etc/cableplan/git/known_hosts -o StrictHostKeyChecking=yes'
echo 'Ajoutez uniquement cette clé PUBLIQUE dans CablePlan > Settings > Deploy keys (lecture seule) :'
cat "$key.pub"
echo 'Puis relancez avec --verify.'
if [[ ${1:-} == --verify ]]; then
    git --git-dir=/usr/local/src/cableplan.git fetch origin refs/heads/main:refs/heads/main
    echo 'Lecture GitHub validée.'
fi
