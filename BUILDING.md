# Building the add-on

## Local image (amd64)

The Angular Web UI is built by CI before the Docker image; build it locally
first if you want the ingress panel:

```bash
cd meross_local_broker/addon_web_ui
npm ci
npm run build          # output: ../../rootfs/var/www
cd ../..

docker build \
  --build-arg BUILD_ARCH=amd64 \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm \
  -t local/meross_local_broker meross_local_broker
```

Cross-build for arm64:

```bash
docker buildx build --platform linux/arm64 \
  --build-arg BUILD_ARCH=aarch64 \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/aarch64-base-debian:bookworm \
  -t local/meross_local_broker:arm64 meross_local_broker --load
```

The build compiles Mosquitto and its Go auth plugin; it takes time.

## Local Home Assistant add-on

Copy **the `meross_local_broker` folder** (the one with `config.yaml`) as a
direct child of `/addons/`:

```
/addons/meross_local_broker/config.yaml
/addons/meross_local_broker/Dockerfile
/addons/meross_local_broker/rootfs/...
```

Then: Settings → Add-ons → Add-on Store → ⋮ → Check for updates. The add-on
appears under Local add-ons and Supervisor builds it.

## GitHub / GHCR

1. `./configure.sh <github-user> <email>`
2. `./push.sh <github-user>`
3. GitHub → Actions: the builder workflows have `packages: write` and publish
   `ghcr.io/<user>/{arch}-meross_local_broker`.
4. GitHub → Packages → each arch image → Package settings → **Public**.
5. Add the repository URL in HA → Add-ons → Add-on Store → Repositories.

## Tests

The Dockerfile runs `test_http_api`. Locally:

```bash
python3 -m venv .venv
.venv/bin/pip install paho-mqtt==1.5.1 expiringdict SQLAlchemy==1.4.54 \
  meross_iot==0.4.7.5 Flask==3.1.3 Werkzeug==3.1.8 flask-cors==6.0.5 'setuptools<81'
cd meross_local_broker/rootfs/opt/custom_broker
PYTHONPATH=. ../../../../.venv/bin/python -m unittest \
  test_mrs100_roller_shutter test_broker_agent_timezone test_http_api
```

HACS cannot install add-ons; the companion
[Meross Cloud IoT integration](https://github.com/mazkagaz/meross-cloud) is a
separate repository.
