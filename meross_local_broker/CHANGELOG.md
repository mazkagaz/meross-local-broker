## 0.0.1-alpha69

- Add the authenticated `POST /v1/Device/delete` endpoint, so the Android
  pairing app can forget a device owned by the logged-in local account.

## 0.0.1-alpha68

- Keep devices marked online in the HTTP device list when they are connected
  to the local broker. The firmware-reported `system.online.status` can be 0
  when a device is not bound to the Meross cloud, which previously made Home
  Assistant entities unavailable even though MQTT was connected.

## 0.0.1-alpha67

- Add the standard back arrow in the header of Setup, Service status and About
  so these pages return to the paired-devices page.

## 0.0.1-alpha66

- Service logs are decoded with replacement instead of failing with a 500
  when a log contains non-UTF-8 bytes (e.g. nginx binary data).

## 0.0.1-alpha65

- Add **Forget device** to the device menu: removes the device, its channels,
  subdevices and roller-shutter state from the broker database.
- Regenerate the add-on icon from the transparent logo artwork.

## 0.0.1-alpha64

- Fix remaining product-name inconsistencies: the Home Assistant sidebar panel,
  service descriptions and event messages now say **Meross Local Broker**.

## 0.0.1-alpha63

- Refer to the Home Assistant integration as **Meross Local Cloud** in the
  wizard and the installation guide, and document the local-login flow.

## 0.0.1-alpha62

- Rename the add-on to **Meross Local Broker** and add the new banner and icon.
- Remove MRS100 from user-facing titles.

## 0.0.1-alpha61

- Clarify add-on options with names and descriptions in the configuration tab.
- Simplify the Web UI: the device and subdevice tiles are the only front page;
  Setup, Service status and About move to a `...` menu in the top-right.
- Remove the language selector while only English is available.

## 0.0.1-alpha60

- Refer to the Android pairing app as **Meross Local Pairer** in the Web UI
  and documentation.

## 0.0.1-alpha59

- The About page now shows the add-on version declared in `config.yaml`.
  The build workflow copies that version into the Web UI package before
  building, so the displayed value can no longer drift (#10).

## 0.0.1-alpha58

- Fix the upgrade path for accounts created with alpha56 or earlier: their
  password was double-hashed by the admin panel. The first successful login
  now repairs the stored hash transparently, so no account is locked out.

## 0.0.1-alpha57

- Local-only account configuration: remove the Meross Link toggle and the
  cloud federation path. The add-on never contacts or stores Meross cloud
  credentials.
- Clarify the account form: "Login (email or username)", local account only.
- Point the setup wizard to Local Pairer (GitHub Releases) and to the
  `mazkagaz/meross-local-cloud` HACS integration instead of the legacy Play Store app.

## 0.0.1-alpha56

- Fix add-on startup: `get_option` no longer aborts under `set -e` when an
  option is `false` or missing. This repairs `40-api.sh` and `60-nginx.sh`
  exits during container init.

## 0.0.1-alpha55

- Migrate CI to the maintained `home-assistant/builder` composable actions (2026.09.0).
- Build only amd64 and aarch64; the 32-bit architectures are no longer supported by the builder.
- Keep the Web UI build before the Docker image build.

## 0.0.1-alpha53

- Fix the alpha52 startup crash by upgrading Flask to 3.1.3, Werkzeug to 3.1.8, and Flask-CORS to 6.0.5.
- Preserve signed form requests and explicit MQTT authentication denials with Flask 3's stricter JSON handling.
- Check Flask imports and request handling during image builds to catch dependency incompatibilities before release.

## 0.0.1-alpha52

- Push the timezone and DST rules (`Appliance.System.Time`) to devices whose reported timezone is empty or
  different from the configured one, as the Meross cloud does on every connection. Without it, power-metering
  plugs (e.g. mss310, mss210p) keep reporting 0 V / 0 A / 0 W and an empty consumption history (#42).
  New optional `device_timezone` setting, defaulting to the Home Assistant timezone.
- The agent now polls `Appliance.System.All` every 60 seconds from devices whose info is stale. Devices
  reconnecting after a broker restart publish nothing on their own, so without this poll their online status
  (and the timezone check above) never refreshed.
- Fix CICD bulding pipeline

## 0.0.1-alpha46

- Dropped support for armhf platform
- Improved s6 restart procedure
- Updated dependency with meross_iot low level library

## 0.0.1-alpha46

- Add new endpoint to support latest version of MerossIot library version

## 0.0.1-alpha45

- Fix meross link parameter being ingored at configuration phase
