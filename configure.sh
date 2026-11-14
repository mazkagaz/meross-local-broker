#!/usr/bin/env bash
# Fill GitHub/email placeholders in this repository.
# Usage: ./configure.sh <github-user> <email>
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: $0 <github-user> <email>" >&2
  exit 1
fi
USER="$1"
EMAIL="$2"
cd "$(dirname "$0")"

FILES=(
  repository.yaml
  meross_local_broker/config.yaml
  meross_local_broker/build.yaml
  README.md
  MRS100.md
  MRS100_PATCH.md
)

for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  sed -i "s|%3CGITHUB_USER%3E|$USER|g; s|<GITHUB_USER>|$USER|g; s|<YOUR_EMAIL>|$EMAIL|g" "$f"
done

echo "Configured:"
grep -n 'github.com/' repository.yaml README.md meross_local_broker/config.yaml meross_local_broker/build.yaml | head
