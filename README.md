**English** · [Français](README.fr.md)

# Meross Local Broker — Home Assistant add-on

![Meross Local Broker](branding/meross-local-broker-banner.jpeg)

**Unofficial** add-on that replaces the Meross cloud with a local broker for
Home Assistant. It controls Meross devices on the local network, without
depending on the cloud for daily operation.

![aarch64](https://img.shields.io/badge/aarch64-yes-green.svg)
![amd64](https://img.shields.io/badge/amd64-yes-green.svg)

## The three building blocks

| Component               | Role                              | Repository                                                                      |
| ----------------------- | --------------------------------- | ------------------------------------------------------------------------------- |
| **Meross Local Broker** | add-on: MQTT broker + local API   | [mazkagaz/meross-local-broker](https://github.com/mazkagaz/meross-local-broker) |
| **Meross Local Cloud**  | Home Assistant integration (HACS) | [mazkagaz/meross-local-cloud](https://github.com/mazkagaz/meross-local-cloud)   |
| **Meross Local Pairer** | Android pairing app               | [mazkagaz/meross-local-pairer](https://github.com/mazkagaz/meross-local-pairer) |

```
Meross device ──MQTT/TLS──> Meross Local Broker add-on ──API/MQTT──> HA integration
                                      ^
                                      │ initial pairing
                             Meross Local Pairer (Android)
```

## Compatibility

The broker works with Meross devices that accept a local broker. The
**MRS100** (roller shutter) is the validation reference; all other families in
the catalog (power strips, sensors, garage doors, purifier, MST, energy meters,
MSXH0, HP110, MTS9, thermostats…) need testers on real hardware. Open an
[issue](https://github.com/mazkagaz/meross-local-broker/issues) with the model,
firmware and the functions that work or fail. Requests for specific device
families are welcome.

## Version compatibility

| Component                      | Minimum version | Notes                                                |
| ------------------------------ | --------------- | ---------------------------------------------------- |
| Broker                         | 1.4.8           | MRS100 profile 2026.11.4; **1.5.0** for HA Container |
| Meross Local Cloud integration | 3.2.2           | profile engine 2.5.1; Position and typed durations   |
| Meross Local Pairer            | 2.0.9           | HTTPS discovery and pairing only                     |

## Ports

| Port         | Use                                   | Enabled by default |
| ------------ | ------------------------------------- | ------------------ |
| **2001/tcp** | MQTT/TLS (devices)                    | yes                |
| **2003/tcp** | HTTP API, **Supervisor ingress only** | yes                |
| **2004/tcp** | HTTPS API (TLS)                       | yes                |

Port **2003** is no longer reachable from the LAN: it only serves the
**Home Assistant ingress** (web panel and administration through the
Supervisor). LAN clients (HA integration, pairer) use **HTTPS 2004** only.

The administration API (renaming/removing from the web panel, services, logs)
is only reachable through the **Home Assistant ingress**, with the HA user
identity. No debug port is published: `debug_mode` only enables detailed logs.

## Before you start

- Home Assistant OS or Supervised (the add-on needs the Supervisor).
- HACS installed, for the Home Assistant integration.
- A Meross device to pair and a **2.4 GHz WPA2** Wi-Fi network.
- An Android phone for Meross Local Pairer.
- **amd64** or **aarch64** installations only (32-bit architectures are no
  longer built).

## Home Assistant Container (Docker)

The add-on needs the Supervisor. On **Home Assistant Container**, run the
broker as a standalone Docker container instead: see
[docs/guides/DOCKER.md](docs/guides/DOCKER.md). The integration and pairer are
unchanged; only the broker deployment differs.

## Full installation

### 1. Install the add-on

In Home Assistant:

1. **Settings → Add-ons → Add-on store**.
2. Menu **⋮ → Repositories**.
3. Add `https://github.com/mazkagaz/meross-local-broker`.
4. Install **Meross Local Broker**, then start it.

The button below opens the dialog directly:

[![Open your Home Assistant instance](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fmazkagaz%2Fmeross-local-broker)

### 2. Create the broker's local account

1. Open the add-on's **Meross Local Broker** panel.
2. Create a local account, for example `meross-local`, with a password.
3. No Meross cloud credentials are requested: this account stays local.
4. Confirm. The add-on restarts its services.

This account is only used by the local broker. It is not your Meross cloud
account.

If needed, the same operation can be done from the command line (replace the
address and password):

```bash
curl -sk -X PUT https://homeassistant.local:2004/_admin_/configuration \
  -H 'Content-Type: application/json' \
  -d '{"email":"meross-local","password":"LocalPassword"}'
```

The response contains `userId` and `mqttKey`. `userId` is normally `1`.

### 3. Pair a Meross device

Follow the
[Meross Local Pairer](https://github.com/mazkagaz/meross-local-pairer#readme)
procedure. The app configures the device to connect to this add-on.

- **Without Bluetooth LE**: pair through the device's `Meross_*` Wi-Fi AP.
- **With Bluetooth LE** (`MRBL_…` advertisement, especially recent MRS100):
  use Meross Local Pairer's Bluetooth LE pairing.

Once pairing is complete:

- the add-on must log the device connection and its **ONLINE** state;
- the web panel's **Paired devices** page must show the device.

### 4. Install the Home Assistant integration

Follow the
[Meross Local Cloud](https://github.com/mazkagaz/meross-local-cloud#install-with-hacs)
procedure. The integration is installed with **HACS**, then configured with
the broker's local account.

The form asks for the broker address (without `https://`), the HTTPS and MQTT
ports, then the local account. The ports are pre-filled by mDNS discovery.

| Field          | Usual value                                    |
| -------------- | ---------------------------------------------- |
| Broker address | `homeassistant.local` or the Home Assistant IP |
| HTTPS port     | `2004`                                         |
| MQTT port      | `2001`                                         |
| Local login    | the local account, for example `meross-local`  |
| Password       | the local password                             |
| MFA code       | only if the local account requires it          |

The broker must be **1.3.1 or newer**: the integration fetches and pins its CA
(`/ca.crt`). The tuning page requires **1.4.0 or newer**; **1.4.4** makes
profile matching automatic and reliable (manual ability refresh remains
available). **1.4.6** ships the MRS100 `2026.11.3` profile and its movement
icons; **1.4.8** adds the Position entity and typed durations. Install the
**3.2.2** integration first. The “ignore validation” options no longer exist.
The integration's User-Agent option is set in
**Settings → Devices & services → Meross Local Cloud → Configure**.

### TLS

The **2001** MQTT listener and the **2004** HTTPS listener share the same local
certificate authority (`/data/mqtt/certs`). This CA is valid (`CA:TRUE`) and
the server certificate contains the LAN IPs. Port **2003** is plain HTTP but
**reserved for the Supervisor ingress**; the LAN uses HTTPS 2004.

HTTPS is **always enabled**: the integration and the pairer refuse cleartext
HTTP, and port 2003 is only reachable through the Supervisor ingress. An
invalid local CA (created before 1.0.0) is regenerated automatically at
startup, with a backup in `/data/mqtt/certs.bak-*`.

Device publications are checked (signature, freshness, anti-replay) and each
device can only use its own topics. The **`mqtt_integrity_mode`** option
defaults to `observe` (mismatches are logged); switch to `enforce` after a
verification period.

The server certificate is self-signed by the local CA. To validate it on the
client side, fetch the CA from `https://homeassistant.local:2004/ca.crt`,
compare its fingerprint with `/data/mqtt/certs/ca.crt`, then import it. Since
**1.0.0**, the CA is valid (`CA:TRUE`) and the server certificate contains the
LAN IPv4 addresses: the integration and the pairer verify the chain. The
“ignore validation” options have been removed.

### 5. Verify

In Home Assistant, the device must appear with the entities for its type
(plug, light, shutter, etc.).

For an **MRS100**, the integration also creates:

- a `cover` entity for the shutter;
- a **Position** `number` entity (0–100 %);
- two `number` entities for the open/close durations, as typed fields;
- two calibration buttons;
- a **Calibration status** sensor.

## Usage

Devices are controlled with their usual Home Assistant entities. For the
**MRS100**:

- **Open/close**: `cover` entity. Its icon shows an up/down arrow while
  moving, then an open, closed or partial shutter icon at rest.
- **Position**: `number` slider, 0–100 %, synchronized with the cover.
- **Durations**: `number` entities as typed fields (10–120 seconds). Values
  are persisted by the add-on and re-applied after reconnection.
- **Calibration**: **Start calibration** button, then track it in
  **Calibration status** (`in_progress`, `success`, `timeout`,
  `motor_blocked`, `failed_N`). **Stop calibration** interrupts the movement.

In the broker panel, the advanced mode of the **Paired devices** list also
shows the applied profile: its version, and a **Custom** badge when the
profile comes from `/data/device_profiles`. `—` means that no profile is
matched yet; the ability document is then requested automatically.

## Forgetting a device

**Forget device** (add-on Web UI or pairing app) removes the device and
**revokes its MAC**: the device keeps its MQTT credentials, but the broker now
refuses its connection, so it cannot come back on its own.

A successful new pairing calls `POST /v1/Device/claim` to lift the revocation.
The device keeps the same UUID: in Home Assistant, its entities and existing
automations remain valid after a forget/re-pair cycle.

After a forget, the agent publishes the `Appliance.Control.Unbind` event that
removes the entities in Home Assistant. This publication happens at the latest
**60 seconds** after removal (or immediately when the agent reconnects): that
is the normal delay during which entities may still appear.

With integration **3.1.0 or newer**:

- an Unbind received for an active device immediately removes its device entry
  and entities in Home Assistant;
- a device left in the HA registry without being seen by the broker is detected
  at startup; after **48 hours** of absence, a “Device no longer paired” repair
  offers to remove it;
- if the device comes back before that, the repair disappears by itself.

## Options

Options are set in **Settings → Add-ons → Meross Local Broker →
Configuration**. Details are in [DOCS.md](meross_local_broker/DOCS.md) (also
available in [French](meross_local_broker/DOCS.fr.md)).

| Option                | Default   | Purpose                                                      |
| --------------------- | --------- | ------------------------------------------------------------ |
| `advertise`           | `true`    | mDNS advertisement of the broker and HTTPS API               |
| `debug_mode`          | `false`   | detailed logs                                                |
| `device_timezone`     | empty     | timezone (+ DST) pushed to devices; empty = HA timezone      |
| `mqtt_integrity_mode` | `observe` | signature/freshness/anti-replay check of publications        |
| `reinit_db`           | `false`   | erase local account and devices at startup (troubleshooting) |

## Device profiles (advanced mode)

The profile catalog is shipped in the add-on but can be overridden without
rebuilding the image: drop YAML files into `/data/device_profiles`. The same
`id` replaces the bundled profile; a new `id` adds one. An invalid file is
ignored and reported; the bundled profile stays active. Reload with
`POST /_admin_/profiles/reload` (Supervisor ingress); the response lists added,
removed and changed profiles. The integration checks the revision every 60 s;
when it changes, it advertises the update with a persistent notification and
offers manual installation from the profile's `update` entity. The catalog is
signed (Ed25519, key in `/data`) and the integration rejects an invalid
signature. With the advanced profile entities option, each device and
subdevice exposes an `update` entity (applied profile, version,
re-application).

### Capture mode

For a model not yet covered, the administration API (Supervisor ingress) can
temporarily capture device frames: `POST /_admin_/capture/start` with `uuid`,
`type`, then `stop`. Sessions are written to `/data/capture` with restricted
permissions; secrets are removed and identifiers pseudonymized.
`POST /_admin_/capture/draft` produces a YAML draft of the observed
namespaces, to complete and drop into `/data/device_profiles`. Duration and
size are bounded.

### Tuning page

The panel also exposes a **Device tuning** page (tune icon), only through the
Supervisor ingress. It provides:

- **Profiles**: YAML editor with continuous validation and diff, override
  application with backup and optimistic lock, revert to the bundled profile,
  backup restore, YAML/ZIP import/export and audit.
- **Devices**: descriptor, expected entities, polling plan, shutter cache,
  frame simulation, read-only live GET and capture with a draft injected into
  the editor. Profile-declared commands are listed with one-time
  confirmation, a profile-generated payload (never typed raw), one command at
  a time and audit with before/after snapshots.
- **Audit**: action and result history.

The bundled catalog stays read-only; only overrides under
`/data/device_profiles` are written. Full guide:
[`docs/guides/DEVICE-TUNING.md`](docs/guides/DEVICE-TUNING.md).

**No-code example**: add a `Movement` sensor to an MRS100 from a real capture,
as a local override —
[`docs/guides/OVERRIDE-MRS100-MOVEMENT.md`](docs/guides/OVERRIDE-MRS100-MOVEMENT.md).

## Logs

The broker panel shows four status LEDs, one per service. Clicking an LED opens
the **Logs** page on the selected service tab; the Back arrow returns to the
home page. The page offers search (with highlighting) and level filtering,
copying visible lines, downloading the full log, follow/pause and return to the
line. Only the displayed tab queries the API. Agent logs automatically
pseudonymize UUIDs, MAC addresses, IPs, emails and secrets before writing, so
they can be shared without manual masking.

## `device_timezone` setting

The `device_timezone` option pushes the timezone and daylight-saving rules to
devices. Leave empty to use the Home Assistant timezone.

## Troubleshooting

| Problem                                   | Check                                                                    |
| ----------------------------------------- | ------------------------------------------------------------------------ |
| The add-on does not start                 | amd64/aarch64 architecture, Supervisor logs, public GHCR image           |
| No device in the add-on                   | Wi-Fi AP or Bluetooth LE pairing, MQTT port 2001, 2.4 GHz WPA2           |
| The integration cannot see the broker     | HTTPS address 2004, local account, broker 1.3.1+ (1.4.0 for tuning)      |
| Entities missing                          | device ONLINE in the add-on, then restart the integration                |
| Ghost entities after forgetting           | integration 3.1.0+, wait for the 48 h repair or delete the device        |
| Durations not kept                        | `Stored roller-shutter config` / `Re-applied roller-shutter config` logs |
| Device already linked to the Meross cloud | reset the device before local pairing                                    |

## Technical documentation

The technical documentation is currently in French; English translations are
being added progressively.

- [Documentation index](docs/README.md)
- [Architecture overview](docs/architecture/OVERVIEW.md)
- [API contracts](docs/specs/API-CONTRACTS.md)
- [Profile authoring](docs/specs/PROFILE-AUTHORING.md)
- [Add a feature without code — MRS100 example](docs/guides/OVERRIDE-MRS100-MOVEMENT.md)
- [MRS100 roller shutters](docs/specs/MRS100.md)
- [Capture format](docs/specs/CAPTURE-FORMAT.md)
- [Design plans and guides](docs/design/)
- [Test strategy and scenarios](docs/testing/FUNCTIONAL-TESTS.md)
- [Traceability matrix](docs/testing/TRACEABILITY.md)
- [Build and release](docs/operations/BUILDING.md)
- [RELEASE_NOTES.md](RELEASE_NOTES.md) — changes since the fork.
- [docs/device-profiles.schema.json](docs/device-profiles.schema.json) — profile
  schema 2 and examples in [docs/profiles/](docs/profiles/).

## Origin and license

Unofficial fork of
[albertogeniola/ha-meross-local-broker](https://github.com/albertogeniola/ha-meross-local-broker),
under the **Apache License 2.0**. The license text and upstream attribution are
kept in `LICENSE`, `NOTICE`, `MODIFICATIONS.md` and `LEGAL.md`.

This fork is neither affiliated with, approved by, nor sponsored by Meross or
the upstream author. Meross is a trademark of its respective owner.
