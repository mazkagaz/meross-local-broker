#!/usr/bin/env bash
# Smoke test for the standalone (HA Container) mode.
#
# The published image is used as the runtime base; the scripts modified for
# standalone are mounted over it, so the test does not need a full rebuild.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
IMAGE=${IMAGE:-ghcr.io/mazkagaz/amd64-meross_local_broker:1.4.8}
NAME=meross-standalone-smoke
DATA=$(mktemp -d)
LOG=$(mktemp)

cleanup() {
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    rm -rf "$DATA" "$LOG"
}
trap cleanup EXIT

docker pull "$IMAGE" >/dev/null

docker run -d --name "$NAME" --network host \
    -v "$DATA":/data \
    -v "$ROOT/meross_local_broker/rootfs/opt/utils/bashutils.sh":/opt/utils/bashutils.sh:ro \
    -v "$ROOT/meross_local_broker/rootfs/etc/cont-init.d/40-api.sh":/etc/cont-init.d/40-api.sh:ro \
    -v "$ROOT/meross_local_broker/rootfs/etc/cont-init.d/50-mosquitto.sh":/etc/cont-init.d/50-mosquitto.sh:ro \
    -v "$ROOT/meross_local_broker/rootfs/etc/cont-init.d/60-nginx.sh":/etc/cont-init.d/60-nginx.sh:ro \
    -v "$ROOT/meross_local_broker/rootfs/etc/services.d/api/run":/etc/services.d/api/run:ro \
    -v "$ROOT/meross_local_broker/rootfs/etc/services.d/mosquitto/run":/etc/services.d/mosquitto/run:ro \
    -e MEROSS_STANDALONE=1 \
    -e advertise=false \
    -e ADMIN_BIND=127.0.0.1 \
    -e ADMIN_PORT=2003 \
    -e ADMIN_ALLOW_CIDR=127.0.0.1 \
    -e TLS_SAN_AUTO=1 \
    "$IMAGE" >/dev/null

ready=0
for _ in $(seq 1 90); do
    if curl -kfsS https://127.0.0.1:2004/ca.crt >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 2
done
if [[ "$ready" != "1" ]]; then
    docker logs "$NAME" 2>&1 | tail -80
    echo "broker did not become ready" >&2
    exit 1
fi

curl -fsS http://127.0.0.1:2003/ >/dev/null
openssl s_client -connect 127.0.0.1:2001 -brief </dev/null 2>&1 \
    | grep -q "CONNECTION ESTABLISHED"

docker logs "$NAME" >"$LOG" 2>&1
if grep -qi "unbound variable\|No such file or directory" "$LOG"; then
    grep -i "unbound variable\|No such file or directory" "$LOG"
    exit 1
fi

echo "standalone smoke test: OK"
