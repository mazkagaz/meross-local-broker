#!/usr/bin/env bash
# End-to-end Docker test: standalone broker + Home Assistant Container.
#
# Requirements: Docker access, curl, and a Python with aiohttp
# (HA_PYTHON, defaults to python3).
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
CLOUD_ROOT=${CLOUD_ROOT:-$(cd "$ROOT/.." && pwd)/meross-cloud}
HA_PYTHON=${HA_PYTHON:-python3}
BROKER_IMAGE=${BROKER_IMAGE:-ghcr.io/mazkagaz/amd64-meross_local_broker:1.4.8}
HA_IMAGE=${HA_IMAGE:-ghcr.io/home-assistant/home-assistant:stable}
BROKER=e2e-broker-t
HA=e2e-ha-t
NET=e2e-meross-t
WORK=$(mktemp -d)
HA_CONFIG="$WORK/ha-config"
BROKER_DATA="$WORK/broker-data"
R="$ROOT/meross_local_broker/rootfs"

cleanup() {
    docker rm -f "$HA" "$BROKER" >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
    # The containers run as root: remove their files from a throwaway container.
    if [[ -d "$WORK" ]]; then
        docker run --rm -v "$WORK":/work --entrypoint sh "$HA_IMAGE" \
            -c 'rm -rf /work/* /work/.[!.]*' >/dev/null 2>&1 || true
    fi
    rm -rf "$WORK" 2>/dev/null || true
}
trap cleanup EXIT

docker image inspect "$BROKER_IMAGE" >/dev/null 2>&1 || docker pull "$BROKER_IMAGE"
docker image inspect "$HA_IMAGE" >/dev/null 2>&1 || docker pull "$HA_IMAGE"

mkdir -p "$HA_CONFIG/custom_components" "$BROKER_DATA"
cp -a "$CLOUD_ROOT/custom_components/meross_local_cloud" \
    "$HA_CONFIG/custom_components/"
printf 'default_config:\nhomeassistant:\n  name: Test\n' \
    > "$HA_CONFIG/configuration.yaml"

docker network create "$NET" >/dev/null 2>&1 || true
docker run -d --name "$BROKER" --network "$NET" \
    -p 127.0.0.1:2001:2001 -p 127.0.0.1:2003:2003 -p 127.0.0.1:2004:2004 \
    -v "$BROKER_DATA":/data \
    -v "$R/opt/utils/bashutils.sh":/opt/utils/bashutils.sh:ro \
    -v "$R/etc/cont-init.d/40-api.sh":/etc/cont-init.d/40-api.sh:ro \
    -v "$R/etc/cont-init.d/50-mosquitto.sh":/etc/cont-init.d/50-mosquitto.sh:ro \
    -v "$R/etc/cont-init.d/60-nginx.sh":/etc/cont-init.d/60-nginx.sh:ro \
    -v "$R/etc/services.d/api/run":/etc/services.d/api/run:ro \
    -v "$R/etc/services.d/mosquitto/run":/etc/services.d/mosquitto/run:ro \
    -v "$R/usr/local/bin/mosquitto.sh":/usr/local/bin/mosquitto.sh:ro \
    -e MEROSS_STANDALONE=1 \
    -e advertise=false \
    -e ADMIN_BIND=0.0.0.0 \
    -e ADMIN_PORT=2003 \
    -e ADMIN_ALLOW_CIDR=172.16.0.0/12 \
    -e TLS_SAN_EXTRA=127.0.0.1 \
    -e TLS_SAN_AUTO=0 \
    "$BROKER_IMAGE" >/dev/null

for _ in $(seq 1 60); do
    if curl -kfsS https://127.0.0.1:2004/ca.crt >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
curl -kfsS https://127.0.0.1:2004/ca.crt >/dev/null

curl -fsS -X PUT http://127.0.0.1:2003/_admin_/configuration \
    -H 'Content-Type: application/json' \
    -d '{"email":"local-user","password":"secret"}' >/dev/null
sleep 5

docker run -d --name "$HA" --network "container:$BROKER" \
    -v "$HA_CONFIG":/config "$HA_IMAGE" >/dev/null

HA_IP=$(docker inspect -f \
    '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$BROKER")
HA_URL="http://$HA_IP:8123"
for _ in $(seq 1 90); do
    if curl -fsS "$HA_URL/manifest.json" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
curl -fsS "$HA_URL/manifest.json" >/dev/null

HA_URL="$HA_URL" BROKER_HOST=127.0.0.1 "$HA_PYTHON" \
    "$ROOT/tests/docker/ha_test.py"

if docker logs "$HA" 2>&1 | grep -q "Detected blocking call.*meross_local_cloud"; then
    echo "HA detected a blocking call in the integration:" >&2
    docker logs "$HA" 2>&1 | grep -A3 "Detected blocking call.*meross_local_cloud" | head -20 >&2
    exit 1
fi

curl -fsS http://127.0.0.1:2003/_admin_/events?limit=20 \
    | grep -q "logged in via Meross Local API"
echo "docker e2e: OK"
