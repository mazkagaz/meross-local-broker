#!/usr/bin/env bash
# Standalone Meross Local Broker installer for Home Assistant Container.
# Creates .env and ./data, starts the container, then prints the values to
# enter in the Meross Local Cloud integration.
set -euo pipefail
cd "$(dirname "$0")"

die() { echo "error: $*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker is required"
docker compose version >/dev/null 2>&1 || die "docker compose is required"

case "$(uname -m)" in
    x86_64|amd64) ARCH=amd64 ;;
    aarch64|arm64) ARCH=aarch64 ;;
    *) die "unsupported architecture: $(uname -m)" ;;
esac

HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -n "$HOST_IP" ]] || die "no LAN IPv4 address found; set TLS_SAN_EXTRA manually"

mkdir -p data

if [[ ! -f .env ]]; then
    TZ_VALUE=$(cat /etc/timezone 2>/dev/null || true)
    cat > .env <<EOF
BROKER_IMAGE=ghcr.io/mazkagaz/${ARCH}-meross_local_broker:latest
ADVERTISE=false
DEBUG_MODE=false
DEVICE_TIMEZONE=${TZ_VALUE}
MQTT_INTEGRITY_MODE=observe
ADMIN_BIND=127.0.0.1
ADMIN_PORT=2003
ADMIN_ALLOW_CIDR=127.0.0.1
TLS_SAN_AUTO=1
TLS_SAN_EXTRA=${HOST_IP}
EOF
    chmod 600 .env
    echo "Created .env (edit it to change ports, timezone, or SANs)."
fi

if [[ -f data/options.json ]]; then
    echo "warning: data/options.json exists and takes precedence over the environment." >&2
fi

docker compose up -d

echo -n "Waiting for the broker HTTPS endpoint"
ready=0
for _ in $(seq 1 60); do
    if docker exec meross-local-broker curl -kfsS https://127.0.0.1:2004/ca.crt >/dev/null 2>&1; then
        ready=1
        break
    fi
    echo -n "."
    sleep 2
done
echo

if [[ "$ready" != "1" ]]; then
    echo "The broker did not become ready. Check: docker logs meross-local-broker" >&2
    exit 1
fi

cat <<EOF

Meross Local Broker is running.

Home Assistant integration (Settings -> Devices & services -> Add integration):
  Broker address : ${HOST_IP}
  HTTPS port     : 2004
  MQTT port      : 2001
  Login/password : the local account created by the broker setup

Admin UI (host loopback only):
  http://127.0.0.1:2003/
  Remote access: ssh -L 2003:127.0.0.1:2003 <user>@${HOST_IP}

Pairer: use ${HOST_IP} as the broker address (HTTPS 2004 / MQTT 2001).
EOF
