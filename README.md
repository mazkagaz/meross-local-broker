# Meross Local LAN Addon (MRS100 fork)

## MRS100 fork

This fork adds MRS100 / roller-shutter support to the local broker:

- persists and re-applies `Appliance.RollerShutter.Config` (`signalOpen`/`signalClose`);
- caches `RollerShutter.Position/State/Adjust`;
- discovers the cover channel from `System.All`, `System.Ability`, or the `mrs100` type;
- exposes `ability` and a `rollerShutter` object (config/position/adjust) in `/v1/Device/devList`;
- includes Python 3 import fixes.

### Install as an add-on

Settings -> Add-ons -> Add-on Store -> three-dot menu -> Repositories, then add:

```
https://github.com/mazkagaz/meross-local-broker
```

Install **Meross Local Broker Addon (MRS100)**. HACS does not install add-ons;
the companion `meross_cloud` integration is distributed separately.

See `MRS100.md` for the patch details and `MRS100_PATCH.md` for the summary.

See `TESTING.md` for the hardware/unit-test checklist and known validation gaps.




This repository contains the Meross Local LAN addon for HomeAssistant.

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fmazkagaz%2Fmeross-local-broker)

## Add-ons

This repository contains the following add-ons

### [Meross Local Broker](./meross_local_broker)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

<!--

Notes to developers after forking or using the github template feature:
- While developing comment out the 'image' key from 'example/config.yaml' to make the supervisor build the addon
  - Remember to put this back when pushing up your changes.
- When you merge to the 'main' branch of your repository a new build will be triggered.
  - Make sure you adjust the 'version' key in 'example/config.yaml' when you do that.
  - Make sure you update 'example/CHANGELOG.md' when you do that.
  - The first time this runs you might need to adjust the image configuration on github container registry to make it public
- Adjust the 'image' key in 'example/config.yaml' so it points to your username instead of 'home-assistant'.
  - This is where the build images will be published to.
- Rename the example directory.
  - The 'slug' key in 'example/config.yaml' should match the directory name.
- Adjust all keys/url's that points to 'home-assistant' to now point to your user/fork.
- Share your repository on the forums https://community.home-assistant.io/c/projects/9
- Do awesome stuff!
 -->

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg

## License and attribution

This is an **unofficial fork** of
[albertogeniola/ha-meross-local-broker](https://github.com/albertogeniola/ha-meross-local-broker).
Upstream code is Copyright Alberto Geniola and contributors under the
**Apache License 2.0**; the license text is preserved in `LICENSE`.
Fork modifications are Copyright 2026 the MRS100 fork contributors under the
same license. See `NOTICE`, `MODIFICATIONS.md` and `LEGAL.md`.

Meross is a trademark of its respective owner. This fork is not affiliated
with, endorsed by, or sponsored by Meross or the upstream author. No Meross
firmware, APK or account secret is distributed here.
