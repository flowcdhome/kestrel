#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"
command -v pipx >/dev/null || { echo "install pipx first: sudo pacman -S python-pipx"; exit 1; }
pipx install --force --editable .
pipx ensurepath >/dev/null 2>&1 || true
echo "[ok] installed. Next: kestrel import-wmn && kestrel verify --apply && kestrel <nick>"
