# Modifications

- Fork date: 2026-11-13
- Upstream: https://github.com/albertogeniola/ha-meross-local-broker
- Upstream license: Apache License, Version 2.0
- Fork license: Apache License, Version 2.0 (see `LICENSE`)
- Modifications copyright: 2026 the MRS100 fork contributors

## Branding

- Display name: **Meross Local Broker**.
- Banner and icon: originals in `branding/`, generated assets in
  `meross_local_broker/icon.png` and `meross_local_broker/logo.png`.

## Modified upstream files

Each modified source file carries a prominent MRS100-fork notice at the top,
as required by Apache-2.0 section 4(b).

| File                                                                | Change                                                                                       |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `meross_local_broker/rootfs/opt/custom_broker/broker_agent.py`      | Roller-shutter channel discovery, config persistence/replay, ability/position/adjust caching |
| `meross_local_broker/rootfs/opt/custom_broker/db_helper.py`         | New persistence helpers/tables                                                               |
| `meross_local_broker/rootfs/opt/custom_broker/model/db_models.py`   | New roller-shutter/ability tables                                                            |
| `meross_local_broker/rootfs/opt/custom_broker/blueprints/device.py` | `devList` ability and roller-shutter metadata                                                |
| `meross_local_broker/rootfs/opt/custom_broker/authentication.py`    | Python 3 `hashlib` import fix                                                                |
| `meross_local_broker/rootfs/opt/custom_broker/s6.py`                | Removed unused Python 3.12-incompatible `asyncore` import                                    |
| `meross_local_broker/config.yaml`                                   | Fork name/version/image                                                                      |
| `.github/workflows/builder*.yaml`                                   | GHCR `packages: write` permissions                                                           |

## New files

- `meross_local_broker/rootfs/opt/custom_broker/test_mrs100_roller_shutter.py`
- `MRS100.md`, `MRS100_PATCH.md`, `BUILDING.md`, `TESTING.md`, `NOTICE`, `MODIFICATIONS.md`,
  `LEGAL.md`, `configure.sh`, `push.sh`

New files are copyright 2026 the MRS100 fork contributors and licensed under
the Apache License, Version 2.0.
