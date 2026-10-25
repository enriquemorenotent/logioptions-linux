#!/bin/bash
# Configure the signed repository; optionally leave installation to the user.
set -euo pipefail
mode=${1:-install}
[[ "$mode" == install || "$mode" == --repository-only ]] || { echo 'Usage: setup_repository.sh [--repository-only]' >&2; exit 2; }
[[ $EUID == 0 ]] || { echo 'Run this script with sudo.' >&2; exit 1; }
. /etc/os-release
[[ ${ID:-} == ubuntu && ${VERSION_CODENAME:-} == resolute && $(dpkg --print-architecture) == amd64 ]] || { echo 'Requires Ubuntu 26.04 amd64.' >&2; exit 1; }
base=https://enriquemorenotent.github.io/logioptions-linux/apt
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$base/logioptions-linux-archive-keyring.gpg" -o "$tmp/key.gpg"
fingerprint=$(gpg --batch --show-keys --with-colons "$tmp/key.gpg" 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')
[[ "$fingerprint" == 2C0C3D99D883E061C7FB1F5CBC7633DE86BB5E28 ]] || { echo 'Unexpected repository signing key.' >&2; exit 1; }
install -m 644 "$tmp/key.gpg" /usr/share/keyrings/logioptions-linux-archive-keyring.gpg
cat > /etc/apt/sources.list.d/logioptions-linux.sources <<'EOF'
Types: deb
URIs: https://enriquemorenotent.github.io/logioptions-linux/apt
Suites: resolute
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/logioptions-linux-archive-keyring.gpg
EOF
# Retire only this project's dedicated Launchpad source. Keep a backup.
python3 - <<'PY'
from pathlib import Path
import re
for path in Path('/etc/apt/sources.list.d').glob('enriquemorenotent-gmail-ubuntu-logioptions-linux-*.sources'):
    content = path.read_text()
    uris = re.findall(r'^URIs:\s*(.+)$', content, re.M)
    expected = 'https://ppa.launchpadcontent.net/enriquemorenotent-gmail/logioptions-linux/ubuntu'
    if uris and all(uri.strip().rstrip('/') == expected for uri in uris):
        backup = path.with_suffix('.sources.disabled')
        if backup.exists():
            raise SystemExit(f'Backup already exists: {backup}; source left untouched.')
        path.rename(backup)
        print('Disabled former PPA:', path.name)
PY
apt-get update
if [[ "$mode" == install ]]; then
    apt-get install -y logioptions-linux
else
    echo 'Repository ready. No application package was installed or upgraded.'
fi
