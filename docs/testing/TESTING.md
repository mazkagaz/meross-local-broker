# Testing the add-on

This repository is an unofficial fork. Please report issues with the add-on
log, the device model/hardware/firmware, and the pairing method.

## What can be tested without a Meross device

- Build the Docker image (`../operations/BUILDING.md`).
- Run the unit tests (HTTP API, MQTT integrity, timezone sync, MRS100 message
  handling, Unbind publication, disconnect handling, standalone helpers).
- Run the standalone container smoke test and the HA Container end-to-end
  harness (below).
- Start the add-on locally or in Home Assistant and verify that already-paired
  devices still behave as before.

Device paths (channel discovery, `RollerShutter.Adjust/Position` caching,
`signalOpen`/`signalClose` persistence, calibration) require a real device
connected to the local broker.

## Unit tests

The pins live in
`meross_local_broker/rootfs/opt/custom_broker/requirements_ci.txt`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r meross_local_broker/rootfs/opt/custom_broker/requirements_ci.txt
cd meross_local_broker/rootfs/opt/custom_broker
../../../../.venv/bin/python -m pytest -q
```

Expected: **209 passed, 1 skipped, 26 subtests passed**. Coverage includes the
HTTP API, MQTT integrity, profiles, capture, tuning, standalone mode detection
(`test_standalone`), timezone sync and the MRS100 paths.

The Docker image runs `test_http_api` as a build gate.

## Standalone Docker smoke test

`tools/test_standalone_docker.sh` starts the published broker image with the
repository's standalone scripts mounted over it, then checks HTTPS `/ca.crt`,
the admin UI, MQTT over TLS and the absence of startup script errors. It needs
Docker and `curl`; the `Standalone` job of `.github/workflows/ci.yaml` runs
it on push and pull request.

## HA Container end-to-end harness

`tests/docker/run.sh` starts the standalone broker and a real Home Assistant
Container, creates the local account, connects a simulated MRS100 over MQTT,
adds the integration through its config flow and checks that the entry loads,
that the broker matches the `meross.mrs100` profile and records the login.
See `tests/docker/README.md` for the required tools, environment variables,
test accounts, credentials and troubleshooting. The real Supervisor add-on
path is covered by `tests/supervisor/run.sh` (see `tests/supervisor/README.md`). The `E2E Docker` job of `.github/workflows/ci.yaml` runs it on push and pull
requests against `main` and `dev`.

## Hardware test checklist

1. Install the add-on (custom add-on repository or local build). Create the
   local account in the add-on Web UI (e.g. `meross-local`).
2. Pair the device with
   [Meross Local Pairer](https://github.com/mazkagaz/meross-local-pairer).
   The app and the integration use **HTTPS 2004 only**; port 2003 is reserved
   for the Home Assistant Supervisor ingress and is unreachable from the LAN.
   - Firmware 7: pairing through the device AP (`Meross_*`).
   - Firmware 8 / Bluetooth LE: pairing through the `MRBL_*` advertisement.
3. Confirm the device connects: the add-on log shows the device online and the
   broker receives `/appliance/<uuid>/publish`.
4. Install the companion
   [Meross Local Cloud integration](https://github.com/mazkagaz/meross-local-cloud)
   and configure it with the broker address, HTTPS 2004, MQTT 2001 and the
   local account. Confirm the expected entities appear.
5. For a roller shutter: set open/close durations (10–120 s), run the
   calibration buttons and follow the calibration status sensor's allowed
   values (`in_progress`, `success`, `timeout`, `motor_blocked`, `failed_N`).
   Reconnect the device and verify the durations persist.
6. Test forget: use **Forget device** in the Web UI or the pairer. Within
   60 seconds the integration must remove the device and its entities, and the
   agent log must not report `Periodic device refresh failed`.
7. Open the **Logs** page from a status diode: the selected tab follows the
   clicked service, search and level filters work, and switching tabs stops the
   previous stream.
8. Read `/v1/Device/devList` (authenticated) and confirm `ability` and, for a
   roller shutter, `rollerShutter.config/position/adjust`.

## CI et exécution locale

```bash
make install        # dépendances de test épinglées (requirements_ci.txt)
make test           # suite broker via pytest
make lint-profiles  # schéma + cohérence des profils
make reports        # rapport JUnit dans reports/
```

Le workflow `.github/workflows/ci.yaml` exécute les tests, le lint add-on, le
smoke test autonome, le E2E HA Container et le E2E Supervisor sur chaque
push/PR ; un job `gate` rend le statut global vert uniquement si tous
réussissent. Les rapports JUnit sont archivés.

## Known validation gaps

- Every family needs field testers; the MRS100 is only the reference device.
  Report the model, firmware and working functions.
- Multi-channel cover devices: channel 0 is the primary target.
- `mqtt_integrity_mode` stays in `observe` until device logs are clean; then
  `enforce` can be evaluated.

## Scope

This repository contains no Meross firmware, APK, account token or signing key.
Do not attach those to issues.
