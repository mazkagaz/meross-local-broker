#!/usr/bin/env bash
# Smoke test for the image built by the current CI run.
# It intentionally does not mount repository scripts over the image: the point
# is to verify what was packaged, including /var/www/assets/env.js.
set -euo pipefail

IMAGE=${IMAGE:?IMAGE is required}
NAME=meross-image-smoke
DATA=$(mktemp -d)
chmod 755 "$DATA"

cleanup() {
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    if [[ -d "$DATA" ]] && docker image inspect "$IMAGE" >/dev/null 2>&1; then
        docker run --rm -v "$DATA":/data --entrypoint sh "$IMAGE" \
            -c 'rm -rf /data/* /data/.[!.]*' >/dev/null 2>&1 || true
    fi
    rm -rf "$DATA" 2>/dev/null || true
}
trap cleanup EXIT

docker run -d --name "$NAME" --network host \
    -v "$DATA":/data \
    -e MEROSS_STANDALONE=1 \
    -e ADMIN_BIND=127.0.0.1 \
    -e ADMIN_PORT=2003 \
    -e ADMIN_ALLOW_CIDR=127.0.0.1 \
    -e TLS_SAN_AUTO=1 \
    "$IMAGE" >/dev/null

ready=0
for _ in $(seq 1 90); do
    state=$(docker inspect -f '{{.State.Status}}' "$NAME" 2>/dev/null || true)
    if [[ "$state" != "running" ]]; then
        docker logs "$NAME" >&2 || true
        echo "image smoke test: container is ${state:-missing}" >&2
        exit 1
    fi
    if curl -kfsS https://127.0.0.1:2004/ca.crt >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 2
done

if [[ "$ready" != "1" ]]; then
    docker logs "$NAME" >&2 || true
    echo "image smoke test: HTTPS endpoint did not become ready" >&2
    exit 1
fi

# Packaging checks catch UI output regressions that a start-only test can miss.
docker exec "$NAME" test -f /var/www/index.html
docker exec "$NAME" test -f /var/www/assets/env.js
if docker logs "$NAME" 2>&1 | grep -q "s6-svwait: fatal"; then
    docker logs "$NAME" >&2 || true
    echo "image smoke test: s6 reported a fatal timeout" >&2
    exit 1
fi

echo "image smoke test: OK"
