#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'sudo requis'; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo 'Runner x64 requis'; exit 1; }
id cableplan-runner >/dev/null
runner_dir=/home/cableplan-runner/actions-runner
install -d -o cableplan-runner -g cableplan-runner -m 0700 "$runner_dir"
[[ ! -f $runner_dir/.runner ]] || { echo 'Runner déjà configuré.'; exit 0; }
# Resolve the official stable release and verify its published checksum.
metadata=$(mktemp)
archive=$(mktemp)
trap 'rm -f "$metadata" "$archive"' EXIT
curl -fsSL https://api.github.com/repos/actions/runner/releases/latest -o "$metadata"
read -r url digest < <(python3 - "$metadata" <<'PY'
import json,sys
assets=json.load(open(sys.argv[1]))['assets']
a=next(a for a in assets if a['name'].startswith('actions-runner-linux-x64-') and a['name'].endswith('.tar.gz'))
print(a['browser_download_url'],a.get('digest') or '')
PY
)
[[ $url == https://github.com/actions/runner/releases/download/* && $digest == sha256:* ]] || { echo 'Checksum officiel absent : utilisez les commandes vérifiées fournies par GitHub Settings / Actions / Runners.'; exit 1; }
curl -fsSL "$url" -o "$archive"
printf '%s  %s\n' "${digest#sha256:}" "$archive" | sha256sum -c -
tar -xzf "$archive" -C "$runner_dir"
chown -R cableplan-runner:cableplan-runner "$runner_dir"
cd "$runner_dir"
./bin/installdependencies.sh
read -rsp 'Token temporaire GitHub (Settings > Actions > Runners > New) : ' runner_token
printf '\n'
runuser -u cableplan-runner -- ./config.sh --unattended --url https://github.com/pigeonfou/CablePlan --token "$runner_token" --name cableplan-ubuntu --labels cableplan --work _work
unset runner_token
./svc.sh install cableplan-runner
./svc.sh start
