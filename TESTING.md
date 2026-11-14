# Testing the MRS100 add-on fork

This repository is an unofficial fork. Please report issues with the add-on
log, the device model/hardware/firmware, and the pairing method.

## What can be tested without an MRS100

- Build the Docker image (`BUILDING.md`).
- Run the unit tests (MRS100 message handling, timezone sync, HTTP API).
- Start the add-on locally or in Home Assistant and verify that existing Meross
  devices still behave as before.

The MRS100-specific paths (channel discovery, `RollerShutter.Adjust/Position`
caching, `signalOpen`/`signalClose` persistence) require a real MRS100 (or a
compatible roller-shutter device) connected to the local broker.

## Unit tests

```bash
python3 -m venv .venv
.venv/bin/pip install paho-mqtt==1.5.1 expiringdict SQLAlchemy==1.4.54 \
  meross_iot==0.4.7.5 Flask==3.1.3 Werkzeug==3.1.8 flask-cors==6.0.5 'setuptools<81'
cd meross_local_broker/rootfs/opt/custom_broker
PYTHONPATH=. ../../../../.venv/bin/python -m unittest \
  test_mrs100_roller_shutter test_broker_agent_timezone test_http_api
```

Expected: 28 tests OK.

## Hardware test checklist

1. Install the add-on (custom add-on repository or local build). Configure a
   local account in the add-on Web UI (e.g. `meross@local`); disable Meross
   Link for local-only operation.
2. Retrieve the local account `userId`/`key` (add-on data volume
   `/data/database.db`, users table) if your pairing tool wants manual
   credentials. Alternatively point Custom Pairer at the local API
   (`http://<home-assistant>:2003`) and log in with the local account.
3. Pair the MRS100 to the local broker with Custom Pairer (or any client that
   sends `Appliance.Config.Key` + `Appliance.Config.Wifi`).
4. Confirm the device connects: add-on log should show the device online and
   the broker should see `/appliance/<uuid>/publish`.
5. Install the companion `meross_cloud` integration (upstream or the HACS fork)
   and point it at the local API/MQTT; confirm the cover entity appears.
6. Set open/close timings from HA/Custom Pairer. Reconnect the device and
   verify the add-on log:
   - `Stored roller-shutter config ...`
   - `Re-applied roller-shutter config ...`
7. Read `/v1/Device/devList` (authenticated) and confirm:
   - `ability`
   - `rollerShutter.config`
   - `rollerShutter.position`
   - `rollerShutter.adjust`

## Known validation gaps

- The replay of `signalOpen`/`signalClose` has only been unit-tested; it needs
  a real device to confirm the timing persists across reconnects.
- The official app sends `payload.config` as an object (`MRSConfig`);
  `meross_iot` can send `{"config": {...}}`. Verify the device accepts the
  replayed shape before changing the library.
- Multi-channel cover devices are not fully covered: channel 0 is the primary
  target.

## Scope

This repository contains no Meross firmware, APK, account token or signing key.
Do not attach those to issues.
