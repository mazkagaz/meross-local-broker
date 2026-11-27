# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Golden-frame regression tests for the MSL610 light profile."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import profile_engine
from profiles import ProfileCatalog

HERE = Path(__file__).parent
PROFILES = HERE / "device_profiles"
FRAMES = HERE / "test_data" / "msl610_frames.jsonl"


class Msl610CaptureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = ProfileCatalog(str(PROFILES))
        data = catalog.profiles["meross.msl610"]
        meta = profile_engine.ProfileMeta(
            id="meross.msl610",
            version=data["profile"]["version"],
            source="test",
            digest=None,
            requires_engine=None,
            data=data,
        )
        cls.compiled = profile_engine.compile_profile(meta)
        cls.frames = [
            json.loads(line)
            for line in FRAMES.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_captured_frames_update_brightness_and_color_temperature(self):
        self.assertEqual(self.compiled.errors, [])
        runtime = profile_engine.DeviceRuntime("msl610-test", self.compiled)
        for frame in self.frames:
            runtime.dispatch(frame["namespace"], frame["method"],
                             frame["payload"])

        values = runtime.entities["light"].values
        self.assertEqual(values["onoff"], 1)
        self.assertEqual(values["brightness"], 8)
        self.assertEqual(values["color_temp"], 50)

    def test_captured_temperature_values_map_to_the_expected_range(self):
        runtime = profile_engine.DeviceRuntime("msl610-test", self.compiled)
        for temperature in (1, 50, 100):
            runtime.dispatch(
                "Appliance.Control.Light", "PUSH",
                {"light": {"capacity": 6, "channel": 0,
                           "temperature": temperature, "luminance": 50}})
            self.assertEqual(
                runtime.entities["light"].values["color_temp"], temperature)

    def test_color_temperature_command_targets_light_temperature(self):
        command = self.compiled.entities["light"].commands["set_color_temp"]
        self.assertEqual(command.namespace, "Appliance.Control.Light")
        self.assertEqual(command.payload, {
            "channel": "$channel",
            "light": {
                "capacity": 6,
                "temperature": "$value",
                "luminance": "$brightness",
            },
        })

    def test_brightness_command_sets_capacity(self):
        command = self.compiled.entities["light"].commands["set_brightness"]
        self.assertEqual(command.payload, {
            "channel": "$channel",
            "light": {"capacity": 4, "luminance": "$value"},
        })

    def test_light_and_togglex_are_not_polled(self):
        for namespace in (
                "Appliance.Control.Light", "Appliance.Control.ToggleX"):
            methods = self.compiled.namespaces[namespace].methods
            self.assertNotIn("GET", methods)
            self.assertNotIn("GETACK", methods)
