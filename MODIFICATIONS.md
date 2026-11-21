# Modifications

- Upstream: https://github.com/albertogeniola/ha-meross-local-broker
- Upstream license: Apache License, Version 2.0
- Fork license: Apache License, Version 2.0 (see `LICENSE`)
- First public fork commit: 2026-11-15
- Modifications copyright: 2026 the MRS100 fork contributors

## Branding

- Display name: **Meross Local Broker**.
- Banner and icon: unified originals in `branding/` (the logo is a transparent
  PNG); generated assets in `meross_local_broker/icon.png`,
  `meross_local_broker/logo.png`, the web UI banner and favicons.

## Main modified areas

The fork keeps the upstream architecture (Flask API, Mosquitto, s6, agent) and
changes the areas below. The most heavily rewritten source files carry a
prominent fork notice at the top; the full list of behaviour changes is in
`meross_local_broker/CHANGELOG.md`.

| Area                                                                 | Change                                                                                                                                      |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `rootfs/opt/custom_broker/broker_agent.py`                           | MRS100 channel/config persistence and replay, timezone push, Unbind publication, forgotten-device disconnect handling, TLS connection retry |
| `rootfs/opt/custom_broker/db_helper.py`, `model/db_models.py`        | Roller-shutter, ability, pending-unbind and revocation tables/helpers                                                                       |
| `rootfs/opt/custom_broker/blueprints/device.py`                      | `devList` ability/roller-shutter metadata, forget queue                                                                                     |
| `rootfs/opt/custom_broker/blueprints/admin.py`                       | Forgetting from the Web UI, ingress-only administration                                                                                     |
| `rootfs/opt/custom_broker/blueprints/devs.py`                        | Dynamic MQTT authentication and per-device/per-app ACL                                                                                      |
| `rootfs/opt/custom_broker/authentication.py`                         | Argon2id passwords, hashed expiring sessions, Python 3 fixes                                                                                |
| `rootfs/opt/custom_broker/http_api.py`                               | Waitress, error handling, CORS restrictions                                                                                                 |
| `rootfs/opt/custom_broker/mqtt_integrity.py`                         | Signature, freshness and replay checks                                                                                                      |
| `rootfs/opt/custom_broker/rate_limit.py`                             | Login rate limiting                                                                                                                         |
| `rootfs/opt/custom_broker/timezone_utils.py`                         | Timezone/DST payloads                                                                                                                       |
| `rootfs/opt/custom_broker/supervisor_network.py`, `mdns_register.py` | LAN address discovery and mDNS advertisement                                                                                                |
| `rootfs/etc/mosquitto`, `cont-init.d`, `services.d`, `usr/local/bin` | Valid local CA, HTTPS-only LAN access, ingress-only admin API, service scripts                                                              |
| `rootfs/etc/nginx/ingress.conf`                                      | TLS listener, ACLs, ingress routing                                                                                                         |
| `addon_web_ui`                                                       | HA-themed panel, status diodes, paired devices, full-page logs                                                                              |
| `config.yaml`, `Dockerfile`, `.github/workflows`                     | Options, image build, amd64/aarch64 only, GHCR publication                                                                                  |

## New files

- Tests: `test_http_api.py`, `test_mqtt_integrity.py`,
  `test_supervisor_network.py`, `test_timezone_utils.py`,
  `test_mrs100_roller_shutter.py`, `test_broker_agent_timezone.py`,
  `test_broker_agent_unbind.py`, `test_broker_agent_disconnect.py`.
- Documentation: `README.md`, `docs/specs/MRS100.md`, `docs/design/MRS100_PATCH.md`, `docs/testing/TESTING.md`,
  `docs/operations/BUILDING.md`, `RELEASE_NOTES.md`, `MODIFICATIONS.md`, `LEGAL.md`, `NOTICE`.
- Tooling: `configure.sh`, `push.sh`, `branding/`.

New files are copyright 2026 the MRS100 fork contributors and licensed under
the Apache License, Version 2.0.
