# Testing the add-on

This repository is an unofficial fork. Please report issues with the add-on
log, the device model/hardware/firmware, and the pairing method.

## What can be tested without a Meross device

- Build the Docker image (`../operations/BUILDING.md`).
- Run the unit tests (HTTP API, MQTT integrity, timezone sync, MRS100 message
  handling, Unbind publication, disconnect handling).
- Start the add-on locally or in Home Assistant and verify that already-paired
  devices still behave as before.

Device paths (channel discovery, `RollerShutter.Adjust/Position` caching,
`signalOpen`/`signalClose` persistence, calibration) require a real device
connected to the local broker.

## Unit tests

The pins live in
`meross_local_broker/rootfs/opt/custom_broker/requirements.txt`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r meross_local_broker/rootfs/opt/custom_broker/requirements.txt
cd meross_local_broker/rootfs/opt/custom_broker
PYTHONPATH=. ../../../../.venv/bin/python -m unittest discover -p 'test_*.py'
```

Expected: **74 tests OK**. Modules: `test_http_api`, `test_mqtt_integrity`,
`test_supervisor_network`, `test_timezone_utils`, `test_mrs100_roller_shutter`,
`test_broker_agent_timezone`, `test_broker_agent_unbind`,
`test_broker_agent_disconnect`.

The Docker image runs `test_http_api` as a build gate.

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

Le workflow `.github/workflows/test.yaml` exécute le linter de profils puis
la suite broker sur chaque push/PR ; les rapports JUnit sont archivés.

## Known validation gaps

- Every family needs field testers; the MRS100 is only the reference device.
  Report the model, firmware and working functions.
- Multi-channel cover devices: channel 0 is the primary target.
- `mqtt_integrity_mode` stays in `observe` until device logs are clean; then
  `enforce` can be evaluated.

## Scope

This repository contains no Meross firmware, APK, account token or signing key.
Do not attach those to issues.
