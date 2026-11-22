# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Parity checks for the shared profile engine vendored from the
integration."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

import profile_engine
from profiles import ProfileCatalog

PROFILES = Path(__file__).with_name("device_profiles")
FILES = (
    "compiler.py",
    "constants.py",
    "match.py",
    "models.py",
    "paths.py",
    "registry.py",
    "runtime.py",
)


class SharedProfileEngineTest(unittest.TestCase):
    def test_every_bundled_profile_compiles(self):
        catalog = ProfileCatalog(str(PROFILES))
        self.assertEqual(catalog.errors, [])
        self.assertTrue(catalog.profiles)

        for profile_id, data in catalog.profiles.items():
            with self.subTest(profile=profile_id):
                profile = profile_engine.ProfileMeta(
                    id=profile_id,
                    version=data["profile"].get("version"),
                    source="test",
                    digest=None,
                    requires_engine=None,
                    data=data,
                )
                compiled = profile_engine.compile_profile(profile)
                self.assertEqual(compiled.errors, [])
                self.assertTrue(
                    compiled.entities or compiled.subdevices,
                    f"{profile_id} exposes no entity or template")

    def test_runtime_golden_frames(self):
        profile = profile_engine.ProfileMeta(
            id="meross.mrs100",
            version="test",
            source="test",
            digest=None,
            requires_engine=None,
            data=ProfileCatalog(str(PROFILES)).profiles["meross.mrs100"],
        )
        compiled = profile_engine.compile_profile(profile)
        runtime = profile_engine.DeviceRuntime("u1", compiled)

        self.assertEqual(runtime.dispatch(
            "Appliance.RollerShutter.Position", "PUSH",
            {"position": [{"channel": 0, "position": 42}]}), 1)
        self.assertEqual(
            runtime.entities["cover"].values["position"], 42)

        self.assertEqual(runtime.dispatch(
            "Appliance.RollerShutter.Adjust", "PUSH",
            {"adjust": [{"channel": 0, "status": 2}]}), 1)
        self.assertEqual(
            runtime.entities["calibration_status"].values["value"], 2)

        self.assertEqual(runtime.dispatch(
            "Appliance.RollerShutter.State", "PUSH",
            {"state": [{"channel": 0, "state": 2,
                        "timestamp": 1795356738}]}), 1)
        self.assertEqual(
            runtime.entities["cover"].values["movement"], 2)

    def test_vendored_modules_match_the_integration(self):
        source_root = os.environ.get("MEROSS_CLOUD_REPO")
        if not source_root:
            self.skipTest("MEROSS_CLOUD_REPO is not set")
        source = (Path(source_root) / "custom_components/meross_cloud"
                  / "profiles")
        vendored = Path(profile_engine.__file__).with_name(
            "compiler.py").parent
        self.assertTrue(source.is_dir(), f"missing source {source}")
        for name in FILES:
            with self.subTest(file=name):
                self.assertEqual(
                    (source / name).read_bytes(),
                    (vendored / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
