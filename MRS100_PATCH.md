# MRS100 fork

This is an Apache-2.0 fork of `albertogeniola/ha-meross-local-broker` with a
narrow MRS100/roller-shutter patch:

- creates the cover channel (System.All digest, System.Ability, or MRS100
  device type);
- persists `Appliance.RollerShutter.Config` SET commands from the app/HA and
  re-applies them after reconnect/System.All, emulating the Meross cloud;
- caches `Appliance.RollerShutter.Position/State` and
  `Appliance.RollerShutter.Adjust` reports per channel;
- caches `Appliance.System.Ability` and exposes it, plus a `rollerShutter`
  object (config/position/adjust), in `/v1/Device/devList`;
- fixes the Python 3 `_sha256` import in the auth stack and removes the
  Python 3.12-incompatible unused `asyncore` import.

The upstream paho 1.x / `meross_iot==0.4.7.5` pins are intentionally kept. The
HA `meross_cloud` component keeps its own `meross_iot==0.4.9.2` dependency.

Tests:

```
cd meross_local_broker/rootfs/opt/custom_broker
PYTHONPATH=. .venv/bin/python -m unittest \
    test_mrs100_roller_shutter test_broker_agent_timezone -v
```

Tests including the Dockerfile gate: `test_mrs100_roller_shutter`,
`test_broker_agent_timezone` (19) and `test_http_api` (9).

Full patch details: `MRS100.md`.
Build, GitHub, GHCR and add-on store instructions: `BUILDING.md`.
