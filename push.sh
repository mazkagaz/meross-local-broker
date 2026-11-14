#!/usr/bin/env bash
# Initialize and push this add-on repository.
# Usage: ./push.sh <github-user>   (default branch: main)
set -euo pipefail

USER="${1:?usage: $0 <github-user> <user-email>}"
EMAIL="${2:?usage: $0 <github-user> <user-email>}"
cd "$(dirname "$0")"

if grep -Rq '<GITHUB_USER>' repository.yaml meross_local_broker/config.yaml 2>/dev/null; then
  echo "Placeholders still present; run ./configure.sh <user> <email> first." >&2
  exit 1
fi

if [ ! -d .git ]; then
  git init -b main
  git config user.name ${USER}
  git config user.email ${EMAIL}
fi
git add .
git commit -m "MRS100 roller-shutter support for the local Meross broker" || true
git remote remove origin 2>/dev/null || true
git remote add origin "github.com-meross-local-broker:${USER}/meross-local-broker.git"
git push -u origin main

cat <<EOF

Pushed. Next:
  1. GitHub -> Actions: ensure the Builder workflows have packages: write.
  2. Wait for the GHCR build, then set the packages (amd64/aarch64/armv7/i386)
     to Public in GitHub -> Packages.
  3. Add the repo URL in HA -> Settings -> Add-ons -> Add-on Store -> Repositories:
     https://github.com/${USER}/meross-local-broker
EOF
