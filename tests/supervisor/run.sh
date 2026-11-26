#!/usr/bin/env bash
# End-to-end test of the broker as a real Home Assistant add-on.
#
# A Supervisor container is started as in Home Assistant's own CI, a local
# add-on is built from the published image plus this repository's rootfs, then
# installed and started. Requires Docker and privileged containers.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BASE_IMAGE=${BASE_IMAGE:-ghcr.io/mazkagaz/amd64-meross_local_broker:1.4.8}
SUPERVISOR_IMAGE=${SUPERVISOR_IMAGE:-ghcr.io/home-assistant/amd64-hassio-supervisor:latest}
WORK=$(mktemp -d)
ADDON=meross_broker_ci
SUPERVISOR=hassio_supervisor_ci

cleanup() {
    if [[ "${KEEP:-0}" == "1" ]]; then
        echo "KEEP=1: containers and $WORK kept for inspection" >&2
        return 0
    fi
    docker rm -f "$SUPERVISOR" "addon_local_${ADDON}" hassio_cli >/dev/null 2>&1 || true
    docker network rm hassio >/dev/null 2>&1 || true
    if [[ -d "$WORK" ]] && docker image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
        docker run --rm -v "$WORK":/work --entrypoint sh "$BASE_IMAGE" \
            -c 'rm -rf /work/* /work/.[!.]*' >/dev/null 2>&1 || true
    fi
    rm -rf "$WORK" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$WORK/data" "$WORK/os" "$WORK/addons/local/$ADDON"
cp -a "$ROOT/meross_local_broker/rootfs" "$WORK/addons/local/$ADDON/rootfs"

cat > "$WORK/addons/local/$ADDON/config.yaml" <<'YAML'
name: Meross Local Broker CI
version: "1.5.0"
slug: meross_broker_ci
description: Local add-on used by the CI end-to-end test
arch:
  - amd64
init: false
startup: services
boot: manual
ports:
  2001/tcp: 2001
  2004/tcp: 2004
ports_description:
  2001/tcp: MQTT broker
  2004/tcp: HTTPS API
ingress: true
ingress_port: 2003
panel_icon: mdi:power-socket-us
host_dbus: false
hassio_api: true
options:
  reinit_db: false
  advertise: false
  debug_mode: false
  device_timezone: ""
  mqtt_integrity_mode: "observe"
schema:
  reinit_db: "bool"
  advertise: "bool"
  debug_mode: "bool"
  device_timezone: "str?"
  mqtt_integrity_mode: "list(observe|enforce)"
YAML

cat > "$WORK/addons/local/$ADDON/Dockerfile" <<'DOCKERFILE'
ARG BUILD_FROM
FROM ${BUILD_FROM}
COPY rootfs/ /
DOCKERFILE

cat > "$WORK/addons/local/$ADDON/build.yaml" <<YAML
build_from:
  amd64: ${BASE_IMAGE}
YAML

docker pull "$SUPERVISOR_IMAGE" >/dev/null
docker pull "$BASE_IMAGE" >/dev/null

docker rm -f "$SUPERVISOR" >/dev/null 2>&1 || true
docker network rm hassio >/dev/null 2>&1 || true
docker create --name "$SUPERVISOR" \
    --privileged \
    --security-opt seccomp=unconfined \
    --security-opt apparmor=unconfined \
    -v /var/run/docker.sock:/run/docker.sock:rw \
    -v /run/dbus:/run/dbus:ro \
    -v "$WORK/os:/run/os:rw" \
    -v "$WORK/data:/data:rw,slave" \
    -v /etc/machine-id:/etc/machine-id:ro \
    -v "$WORK/addons:/addons:rw" \
    -e SUPERVISOR_SHARE="$WORK/data" \
    -e SUPERVISOR_NAME="$SUPERVISOR" \
    -e SUPERVISOR_DEV=1 \
    -e SUPERVISOR_MACHINE=qemux86-64 \
    "$SUPERVISOR_IMAGE" >/dev/null
docker start "$SUPERVISOR" >/dev/null

fail() {
    echo "$*" >&2
    docker logs --tail 80 "$SUPERVISOR" >&2 || true
    docker logs --tail 80 "addon_local_${ADDON}" >&2 || true
    exit 1
}

SUP_IP=""
for _ in $(seq 1 150); do
    SUP_IP=$(docker inspect --format='{{.NetworkSettings.Networks.hassio.IPAddress}}' "$SUPERVISOR" 2>/dev/null || true)
    if [[ -n "$SUP_IP" && "$SUP_IP" != "<no value>" ]] \
        && curl -sf "http://$SUP_IP/supervisor/ping" | grep -q '"result": *"ok"'; then
        break
    fi
    sleep 2
done
[[ -n "$SUP_IP" ]] || fail "Supervisor did not start"
curl -sf "http://$SUP_IP/supervisor/ping" | grep -q '"result": *"ok"' \
    || fail "Supervisor API did not answer"

for _ in $(seq 1 120); do
    if docker exec "$SUPERVISOR" true >/dev/null 2>&1 \
        && docker exec "$SUPERVISOR" test -S /run/docker.sock >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

# The CLI plugin is installed by the Supervisor itself.
for _ in $(seq 1 150); do
    if docker exec hassio_cli true >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

run_ha() {
    docker exec hassio_cli ha "$@" --no-progress --raw-json
}

# Wait for the Core install job started by the Supervisor.
for _ in $(seq 1 180); do
    core=$(run_ha core info 2>/dev/null | jq -r '.data.version // empty' 2>/dev/null || true)
    jobs=$(run_ha jobs info 2>/dev/null \
        | jq -r '.data.jobs[] | select(.name == "home_assistant_core_install" and .done == false) | .name' \
        2>/dev/null || true)
    if [[ -n "$core" && "$core" != "landingpage" && -z "$jobs" ]]; then
        break
    fi
    sleep 5
done

echo "Installing local add-on..."
if ! run_ha addons install "local_${ADDON}" >/tmp/addon-install.json 2>&1; then
    cat /tmp/addon-install.json >&2
    fail "add-on installation failed"
fi
run_ha addons start "local_${ADDON}" >/dev/null \
    || fail "add-on start failed"

state=""
for _ in $(seq 1 120); do
    state=$(run_ha addons info "local_${ADDON}" 2>/dev/null | jq -r '.data.state // empty' 2>/dev/null || true)
    [[ "$state" == "started" ]] && break
    sleep 2
done
[[ "$state" == "started" ]] || fail "add-on did not start (state=$state)"

ready=0
for _ in $(seq 1 90); do
    if curl -kfsS https://127.0.0.1:2004/ca.crt >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 2
done
[[ "$ready" == "1" ]] || fail "broker HTTPS endpoint did not become ready"

timeout 5 openssl s_client -connect 127.0.0.1:2001 -brief </dev/null >/dev/null 2>&1 \
    || fail "MQTT TLS listener did not become ready"

docker logs "addon_local_${ADDON}" >/tmp/addon.log 2>&1 || true
grep -q "Substituting ingress_entry" /tmp/addon.log \
    || fail "add-on did not use the Supervisor ingress path"
if grep -q "Standalone mode:" /tmp/addon.log; then
    fail "add-on unexpectedly started in standalone mode"
fi

echo "supervisor e2e: OK"
