# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Tests for the shared device-to-profile matching."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

import profile_match
from profiles import ProfileCatalog

PROFILES = Path(__file__).with_name("device_profiles")


def device(uuid, device_type, abilities):
    return SimpleNamespace(
        uuid=uuid,
        device_type=device_type,
        sub_type=None,
        mac="AABBCCDDEEFF",
        child_subdevices=[],
        _abilities=abilities,
    )


def ability_getter(row):
    return lambda uuid: SimpleNamespace(ability_json=json.dumps(row))


class ProfileMatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.catalog = ProfileCatalog(str(PROFILES))

    def test_matches_a_roller_shutter_from_its_abilities(self):
        roller = device("roller", "mrs100",
                        {"Appliance.RollerShutter.State": {}})
        matches = profile_match.match_devices(
            self.catalog, [roller], ability_getter({
                "Appliance.RollerShutter.State": {}}))
        info = matches["roller"]
        self.assertEqual(info["id"], "meross.mrs100")
        self.assertEqual(info["source"], "bundled")
        self.assertTrue(info["version"])

    def test_requires_the_declared_abilities(self):
        roller = device("roller", "mrs100", {})
        matches = profile_match.match_devices(
            self.catalog, [roller], ability_getter({}))
        self.assertIsNone(matches["roller"])

    def test_reports_an_override_source(self):
        overrides = Path(self.temporary.name) / "overrides"
        overrides.mkdir()
        source = PROFILES / "mrs100.yaml"
        data = yaml.safe_load(source.read_text())
        data["profile"]["version"] = "custom-1"
        (overrides / "mrs100.yaml").write_text(
            yaml.safe_dump(data, sort_keys=False))
        catalog = ProfileCatalog(str(PROFILES), str(overrides))

        roller = device("roller", "mrs100",
                        {"Appliance.RollerShutter.State": {}})
        matches = profile_match.match_devices(
            catalog, [roller], ability_getter({
                "Appliance.RollerShutter.State": {}}))
        info = matches["roller"]
        self.assertEqual(info["source"], "override")
        self.assertEqual(info["version"], "custom-1")


if __name__ == "__main__":
    unittest.main()
