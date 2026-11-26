**English** · [Français](DOCS.fr.md)

# Meross Local Broker

This add-on replaces the Meross cloud with a local broker (MQTT/TLS +
HTTP/HTTPS API) for Home Assistant. HTTPS is enabled by default. It is intended
to be used with:

- [Meross Local Pairer](https://github.com/mazkagaz/meross-local-pairer) to pair
  a Meross device;
- [Meross Local Cloud](https://github.com/mazkagaz/meross-local-cloud) to create
  the Home Assistant entities.

The broker targets all Meross devices that accept a local broker. The
**MRS100** (roller shutter) is the reference; all other families in the catalog
need testers on real hardware. Please report your tests with the model,
firmware and available functions: open an issue on the broker repository.
Requests for specific device families are welcome.

## Starting

1. Start the add-on.
2. Open its panel and create a **local account** (login and password).
3. This account is strictly local: no Meross cloud credentials are used.
4. Pair the device with Meross Local Pairer.
5. Add the Home Assistant integration and configure it with the local account.
   It only works with this local broker; no cloud mode is offered.

> Not using the add-on? On **Home Assistant Container**, run the broker as a
> standalone Docker container: see the
> [Docker guide](../docs/guides/DOCKER.md).

The add-on exposes:

- **2001/tcp**: MQTT broker (TLS, always enabled);
- **2003/tcp**: HTTP API reserved for the Home Assistant (Supervisor) ingress,
  not reachable from the LAN;
- **2004/tcp**: HTTPS API (TLS, always enabled).

Meross Local Pairer and the integration use **HTTPS 2004** exclusively. Port
**2003** is no longer reachable from the LAN: it only serves the Supervisor
ingress for the web panel and administration.

The web panel administration API is only reachable through the Home Assistant
ingress, with the HA user identity. No debug port is published: `debug_mode`
only enables detailed logs.

## Options

- **`advertise`** (`true`): advertises the MQTT broker and the **HTTPS** API via
  mDNS. Keep it enabled unless mDNS is unavailable on the network.
- **`reinit_db`** (`false`): erases the local account and paired devices at
  startup (troubleshooting only).
- **`device_timezone`** (empty): IANA timezone pushed to devices (see below).
- **`debug_mode`** (`false`): detailed logs (`DEBUG` level).
- **`mqtt_integrity_mode`** (`observe`): checks every device publication:

  - signature `md5(messageId + mqttKey + timestamp)`;
  - timestamp within ±900 s;
  - anti-replay by `device:messageId:signature`.

  `observe` logs mismatches and lets the message through; `enforce` rejects it.
  Keep `observe` for at least one release before enabling `enforce`.

Each MQTT device is limited to its own topics
(`/appliance/<uuid>/publish` and `/appliance/<uuid>/subscribe`); an app account
can only publish to the devices it owns.

## `device_timezone` option

IANA timezone (for example `Europe/Paris`) sent to devices with daylight-saving
rules, like the Meross cloud does. Leave empty to use the Home Assistant
timezone.

Without a timezone, some measuring devices (mss310, mss210p plugs, etc.) report
no voltage, current or consumption.

## HTTPS and certificate

Ports **2001** (MQTT/TLS) and **2004** (HTTPS) use the same local certificate
authority, stored in `/data/mqtt/certs`. This CA is valid
(`basicConstraints=CA:TRUE`) and can be imported to verify the broker.

The server certificate contains `homeassistant.local`, `localhost`, `127.0.0.1`
and the detected LAN IPv4 addresses. It is re-signed automatically when those
addresses change. Meross Local Pairer pins the certificate on first contact:
after a broker update or address change, the pin may need to be reset in the
app settings.

The CA passphrase is random and stored in `/data/mqtt/certs/ca.pass`. Old
invalid CAs (without `CA:TRUE`) or CAs close to expiration are regenerated
automatically, with a backup in `/data/mqtt/certs.bak-*`. The CA can be
downloaded from `https://homeassistant.local:2004/ca.crt`.

## Quick checks

- Device connected: open **Paired devices** in the web panel (reachable only
  through the Home Assistant ingress).
- Add-on log: search for `ONLINE`. For an MRS100, the
  `Stored roller-shutter config` / `Re-applied roller-shutter config` messages
  confirm that durations are persisted.
- The MQTT broker must be reachable on port 2001 and the HTTPS API on 2004 from
  the LAN.

## Logs

Clicking one of the four LEDs on the panel opens the **Logs** page on the
selected service tab. The Back arrow returns to the home page. The page offers
search with highlighting, level filtering, copying visible lines, downloading
the full log, pause/follow and return to the line. Only the displayed tab
queries the API.

## Forgetting a device

**Forget device** revokes the MAC and publishes `Appliance.Control.Unbind` to
the Home Assistant integration, at the latest 60 seconds after removal. The
integration then removes the device and its entities; a device that disappears
without an Unbind is proposed for removal after 48 hours.

## Device tuning

The **tune** icon opens the tuning page (Supervisor ingress only): profile
editing with validation and diff, overrides with backup and revert to the
bundled profile, import/export, device state, frame simulation, read-only live
GET, capture and typed commands with confirmation. The bundled catalog stays
read-only; only overrides under `/data/device_profiles` are written. Available
since broker 1.4.0; profile matching, which depends on the device ability
document, is automatic and reliable since 1.4.4 as soon as the device is
online. The **Refresh ability** button remains available as a fallback on the
device page. The main panel (advanced mode) shows the applied profile version
and a **Custom** badge for an override. Since 1.4.8, the MRS100 `2026.11.4`
profile carries the shutter movement, the Position entity and typed durations;
with integration 3.2.2, a new profile version triggers a persistent
notification and a manual installation from the `update` entity.

## Troubleshooting

| Problem                    | Check                                                        |
| -------------------------- | ------------------------------------------------------------ |
| The device does not appear | pairing completed, 2.4 GHz WPA2 Wi-Fi, port 2001             |
| Authentication refused     | local account credentials, `UserId`/`mqttKey`                |
| Entities missing in HA     | integration configured with the local account, broker 1.3.1+ |
| Ghost entities             | integration 3.1.0+, 48 h repair or manual deletion           |
| Zero consumption           | `device_timezone` set or correct HA timezone                 |
| MRS100 durations lost      | `Stored` / `Re-applied` logs, device reconnection            |

## License

Unofficial fork, Apache-2.0. See `NOTICE`, `MODIFICATIONS.md` and `LEGAL.md`.
