# Building the add-on

## Local image (amd64)

The Angular Web UI is built by CI before the Docker image. A local image build
**requires the UI to be generated first**; otherwise the Dockerfile now stops
with an explicit error. Use **Node 22**, as CI does:

```bash
cd meross_local_broker/addon_web_ui
npm ci
npm run build          # output: ../rootfs/var/www
cd ../..
test -f meross_local_broker/rootfs/var/www/index.html
test -f meross_local_broker/rootfs/var/www/assets/env.js
```

Do not commit the generated `rootfs/var/www` files. The Dockerfile checks both
required files before the image is built.

```bash
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
2. `./push.sh <github-user> <email>`
3. GitHub → Actions: the builder workflows have `packages: write` and publish
   `ghcr.io/<user>/{arch}-meross_local_broker`.
4. GitHub → Packages → each arch image → Package settings → **Public**.
5. Add the repository URL in HA → Add-ons → Add-on Store → Repositories.

## Tests

The Dockerfile runs `test_http_api` as a build gate. Locally, install the
pinned requirements and run the whole suite:

```bash
python3 -m venv .venv
.venv/bin/pip install -r meross_local_broker/rootfs/opt/custom_broker/requirements_ci.txt
cd meross_local_broker/rootfs/opt/custom_broker
../../../../.venv/bin/python -m pytest -q
```

Expected: **229 passed, 1 skipped, 27 subtests passed**.

HACS cannot install add-ons; the companion
[Meross Local Cloud integration](https://github.com/mazkagaz/meross-local-cloud) is a
separate repository.
