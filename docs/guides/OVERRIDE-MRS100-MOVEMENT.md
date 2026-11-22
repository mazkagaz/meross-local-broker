**English** · [Français](OVERRIDE-MRS100-MOVEMENT.fr.md)

# Add a feature without code — MRS100 example

This method adds an entity to an existing device **without changing the broker
code or the bundled catalog**. Everything goes through a local profile override
and the tuning page.

The example adds a diagnostic **Movement** sensor to the MRS100, fed by the
`Appliance.RollerShutter.State` PUSH messages the device sends when it is
operated at the wall. It is a proof of concept: a new feature, validated on a
real capture, without rebuilding the image.

## 1. Capture the real behaviour

1. Open **Device tuning** (tune icon, Supervisor ingress).
2. **Devices** tab, select the shutter, then **Start capture**.
3. Lower the shutter at the wall, stop it, then raise it.
4. **Stop**, then **Download ZIP**.

A real MRS100 capture contains for example:

| t (s) | Dir | Namespace                          | Payload                  |
| ----- | --- | ---------------------------------- | ------------------------ |
| 3.66  | rx  | `Appliance.RollerShutter.State`    | `state=2` (closing)      |
| 8.69  | rx  | `Appliance.RollerShutter.Position` | `position=84`            |
| 9.71  | rx  | `Appliance.RollerShutter.State`    | `state=0`, `stoppedBy=1` |
| 11.76 | rx  | `Appliance.RollerShutter.State`    | `state=1` (opening)      |
| 16.78 | rx  | `Appliance.RollerShutter.Position` | `position=100`           |
| 17.80 | rx  | `Appliance.RollerShutter.State`    | `state=0`, `stoppedBy=0` |

Lessons:

- `Appliance.RollerShutter.State` gives the **direction immediately**:
  `0` = stop, `1` = open, `2` = close.
- The `timestamp` and `stoppedBy` fields accompany real PUSH messages; they are
  not needed for the mapping, but useful to document.
- `Position` is sparser (84 %, then 100 %): do not rely on it for instant
  feedback.

## 2. Choose the mapping

The `State` payload is an array, like `Position`:

```json
{ "state": [{ "channel": 0, "state": 2, "timestamp": 1795356738 }] }
```

The shared engine reads a path in the payload. For channel 0, the path is
therefore `state[0].state` — just as the bundled profile uses
`position[0].position` for the cover.

We create a diagnostic `sensor` entity:

- namespace: `Appliance.RollerShutter.State`;
- channel: `0` (so `$channel` in the declaration);
- value: `state[0].state`;
- HA state: `0` stop, `1` open, `2` close (raw values).

## 3. Create the override in the tuning page

Prerequisites: broker with the tuning page, `meross.mrs100` profile matched to
the device and device online.

1. **Profiles** tab, select `meross.mrs100`.
2. The editor contains the effective profile. Add this block at the end of the
   `entities:` list (keep all existing entities):

```yaml
- key: movement
  platform: sensor
  channel: 0
  name: "Movement"
  entity_category: diagnostic
  state:
    namespace: Appliance.RollerShutter.State
    channel: $channel
    fields:
      value: "state[0].state"
```

3. Optional: replace the existing `Appliance.RollerShutter.State` block to
   declare the fields observed in the field:

```yaml
Appliance.RollerShutter.State:
  methods: [GETACK, PUSH]
  fields:
    channel: { type: integer }
    state:
      type: integer
      values: { 0: stop, 1: open, 2: close }
    timestamp: { type: integer }
    stoppedBy: { type: integer }
```

4. **Validate**: the result must have no errors; the diff must only show the
   addition.
5. **Apply override**: confirmation, prior backup and hash lock.
6. The catalog is reloaded. The integration checks the revision every 60 s;
   otherwise restart the integration.

## 4. Verify

**In the tuning page**

- **Devices** tab: the expected `Movement` entity appears.
- **Simulate a frame**: namespace `Appliance.RollerShutter.State`, method
  `PUSH`, payload below. Typed values must show `movement = 1`.

```json
{ "state": [{ "channel": 0, "state": 1, "timestamp": 0 }] }
```

**In Home Assistant**

- After the reload, a diagnostic **Movement** sensor appears.
- A capture or real movement must make it go to `2` (closing), `0` (stop) then
  `1` (opening).

The sensor exposes **raw numeric values**. A dynamic shutter icon or an
“opening/closing” label would require an integration change
(`is_opening` / `is_closing`), not just a profile.

## 5. Revert

- **Revert to bundled** removes the override after a backup.
- Timestamped backups can also restore an earlier version.

The bundled catalog is never modified: the override stays in
`/data/device_profiles`. Once the method is validated, the same entity can be
added to the bundled profile in a later broker release.

The bundled MRS100 profile now uses this signal directly on the cover, through a
`movement` source without a visible entity; this exercise remains the general
method for adding other features through an override.

## Why it works without code

The shared profile engine turns a `namespace + method + channel + path` frame
into entity values. The integration then consumes the entities declared by the
profile. Adding an entity is therefore a configuration operation: no line of
Python is required.
