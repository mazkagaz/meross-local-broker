# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Tests for the bundled device profile catalog.

Run with: python3 -m unittest test_profiles
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import profile_engine
import profiles as profiles_module
from profiles import ProfileCatalog, diff_profiles

HERE = Path(__file__).parent
PROFILES = HERE / "device_profiles"


def minimal(profile_id, version="1", **overrides):
    data = {
        "schema_version": 2,
        "profile": {"id": profile_id, "version": version},
        "match": {"type": ["test"]},
        "payloads": {
            "Appliance.Control.ToggleX": {"methods": ["GETACK"]},
        },
        "entities": [{
            "key": "state",
            "platform": "sensor",
            "state": {
                "namespace": "Appliance.Control.ToggleX",
                "fields": {"value": "onoff"},
            },
        }],
    }
    data.update(overrides)
    return data


class ProfileCatalogTest(unittest.TestCase):
    def test_bundled_catalog_is_valid_and_stable(self):
        first = ProfileCatalog(str(PROFILES))
        second = ProfileCatalog(str(PROFILES))

        self.assertEqual(first.errors, [])
        self.assertEqual(len(first.profiles), 20)
        self.assertEqual(first.revision, second.revision)
        self.assertEqual(len(first.revision), 64)
        self.assertIn("meross.mrs100", first.profiles)

    def test_revision_payload_and_catalog_shape(self):
        catalog = ProfileCatalog(str(PROFILES))

        revision = catalog.revision_payload()
        self.assertEqual(revision["schema_version"], 2)
        self.assertEqual(revision["count"], 20)
        self.assertEqual(revision["errors"], 0)

        payload = catalog.payload()
        self.assertEqual(payload["revision"], catalog.revision)
        ids = sorted(item["id"] for item in payload["profiles"])
        self.assertEqual(ids, [
            "meross.em", "meross.garage", "meross.hp110", "meross.map100",
            "meross.mfc", "meross.mod", "meross.mrs", "meross.mrs100",
            "meross.ms600", "meross.msh300", "meross.msl", "meross.msl120", "meross.msl610", "meross.mss",
            "meross.mss310", "meross.mss425", "meross.mss5", "meross.msxh0", "meross.mts200", "meross.mts300"])
        for item in payload["profiles"]:
            self.assertEqual(item["source"], "bundled")
            self.assertEqual(len(item["hash"]), 64)
            self.assertIn("profile", item)


    def test_msl610_profile_matches_light_and_togglex(self):
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
        result = profile_engine.match_candidates(
            [meta],
            profile_engine.MatchContext(
                type="msl610",
                abilities=frozenset({
                    "Appliance.Control.Light",
                    "Appliance.Control.ToggleX",
                }),
            ),
        )
        self.assertEqual(result.profile.id, "meross.msl610")
        compiled = profile_engine.compile_profile(meta)
        self.assertEqual(compiled.errors, [])
        runtime = profile_engine.DeviceRuntime("msl610-test", compiled)
        self.assertEqual(runtime.dispatch(
            "Appliance.Control.ToggleX", "PUSH",
            {"togglex": [{"channel": 0, "onoff": 1, "lmTime": 1}]}), 1)
        self.assertEqual(runtime.dispatch(
            "Appliance.Control.Light", "PUSH",
            {"light": {"capacity": 6, "channel": 0,
                       "temperature": 50, "luminance": 20}}), 2)
        values = runtime.entities["light"].values
        self.assertEqual(values["onoff"], 1)
        self.assertEqual(values["brightness"], 20)
        self.assertEqual(values["color_temp"], 50)
        command = compiled.entities["light"].commands["set_color_temp"]
        self.assertEqual(command.namespace, "Appliance.Control.Light")
        self.assertEqual(command.payload["light"]["capacity"], 6)
        self.assertEqual(command.payload["light"]["temperature"], "$value")
        self.assertEqual(command.payload["light"]["luminance"],
                         "$brightness")
        brightness = compiled.entities["light"].commands["set_brightness"]
        self.assertEqual(brightness.payload["light"]["capacity"], 4)
        self.assertEqual(brightness.payload["light"]["luminance"], "$value")

    def test_mss_profiles_do_not_poll_togglex(self):
        catalog = ProfileCatalog(str(PROFILES))
        for profile_id in ("meross.mss", "meross.mss310"):
            methods = catalog.profiles[profile_id]["payloads"][
                "Appliance.Control.ToggleX"]["methods"]
            self.assertIn("PUSH", methods)
            self.assertNotIn("GET", methods)
            self.assertNotIn("GETACK", methods)

    def test_mss110_matches_the_generic_mss_profile(self):
        catalog = ProfileCatalog(str(PROFILES))
        meta = profile_engine.ProfileMeta(
            id="meross.mss",
            version=catalog.profiles["meross.mss"]["profile"]["version"],
            source="test",
            digest=None,
            requires_engine=None,
            data=catalog.profiles["meross.mss"],
        )
        result = profile_engine.match_candidates(
            [meta],
            profile_engine.MatchContext(
                type="mss110",
                abilities=frozenset({"Appliance.Control.ToggleX"}),
            ),
        )
        self.assertEqual(result.profile.id, "meross.mss")

    def test_invalid_profile_is_excluded_without_breaking_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            shutil.copy(PROFILES / "schema.json", directory / "schema.json")
            shutil.copy(PROFILES / "mss310.yaml", directory / "mss310.yaml")
            (directory / "broken.yaml").write_text(
                json.dumps({"schema_version": 1}), encoding="utf-8")

            catalog = ProfileCatalog(str(directory))

        self.assertEqual(list(catalog.profiles), ["meross.mss310"])
        self.assertEqual(len(catalog.errors), 1)
        self.assertEqual(catalog.errors[0]["file"], "bundled:broken.yaml")

    def test_extension_keys_survive_and_unknown_core_fields_are_rejected(self):
        entity = {
            "key": "state",
            "platform": "sensor",
            "state": {
                "namespace": "Appliance.Control.ToggleX",
                "fields": {"value": "onoff"},
            },
        }
        good = {
            "schema_version": 2,
            "profile": {"id": "test.good", "version": "1"},
            "match": {"type": ["test"]},
            "payloads": {
                "Appliance.Control.ToggleX": {"methods": ["GETACK"]},
            },
            "entities": [entity],
            "x-vendor": {"source": "capture"},
        }
        bad = {
            "schema_version": 2,
            "profile": {"id": "test.bad", "version": "1"},
            "match": {"type": ["test"]},
            "payloads": {
                "Appliance.Control.ToggleX": {"methods": ["GETACK"]},
            },
            "entities": [entity],
            "surprise": 1,
        }
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            shutil.copy(PROFILES / "schema.json", directory / "schema.json")
            (directory / "good.yaml").write_text(
                json.dumps(good), encoding="utf-8")
            (directory / "bad.yaml").write_text(
                json.dumps(bad), encoding="utf-8")

            catalog = ProfileCatalog(str(directory))
            payload = catalog.payload()

        self.assertEqual(list(catalog.profiles), ["test.good"])
        self.assertEqual([error["file"] for error in catalog.errors],
                         ["bundled:bad.yaml"])
        served = next(item for item in payload["profiles"]
                      if item["id"] == "test.good")
        self.assertEqual(served["profile"]["x-vendor"],
                         {"source": "capture"})


class ProfileOverrideTest(unittest.TestCase):
    def prepare(self, bundled, overrides):
        base = bundled / "schema.json"
        shutil.copy(PROFILES / "schema.json", base)
        for name, data in overrides.items():
            (bundled / name).write_text(json.dumps(data), encoding="utf-8")
        (bundled / "base.yaml").write_text(
            json.dumps(minimal("test.base")), encoding="utf-8")

    def test_override_replaces_bundled_profile(self):
        with tempfile.TemporaryDirectory() as bundled_tmp, \
                tempfile.TemporaryDirectory() as override_tmp:
            bundled, overrides = Path(bundled_tmp), Path(override_tmp)
            self.prepare(bundled, {})
            (overrides / "base.yaml").write_text(
                json.dumps(minimal("test.base", version="2")),
                encoding="utf-8")

            catalog = ProfileCatalog(str(bundled), str(overrides))

        self.assertEqual(catalog.errors, [])
        self.assertEqual(catalog.profiles["test.base"]["profile"]["version"],
                         "2")
        self.assertEqual(catalog.sources["test.base"], "override")
        served = catalog.payload()["profiles"][0]
        self.assertEqual(served["source"], "override")

    def test_invalid_override_keeps_the_bundled_profile(self):
        with tempfile.TemporaryDirectory() as bundled_tmp, \
                tempfile.TemporaryDirectory() as override_tmp:
            bundled, overrides = Path(bundled_tmp), Path(override_tmp)
            self.prepare(bundled, {})
            (overrides / "broken.yaml").write_text(
                json.dumps({**minimal("test.base", version="2"),
                            "surprise": 1}), encoding="utf-8")

            catalog = ProfileCatalog(str(bundled), str(overrides))

        self.assertEqual(catalog.profiles["test.base"]["profile"]["version"],
                         "1")
        self.assertEqual(catalog.sources["test.base"], "bundled")
        self.assertEqual(len(catalog.errors), 1)
        self.assertTrue(catalog.errors[0]["file"].startswith("override:"))

    def test_override_can_add_a_new_profile(self):
        with tempfile.TemporaryDirectory() as bundled_tmp, \
                tempfile.TemporaryDirectory() as override_tmp:
            bundled, overrides = Path(bundled_tmp), Path(override_tmp)
            self.prepare(bundled, {})
            (overrides / "extra.yaml").write_text(
                json.dumps(minimal("test.extra")), encoding="utf-8")

            catalog = ProfileCatalog(str(bundled), str(overrides))

        self.assertEqual(sorted(catalog.profiles),
                         ["test.base", "test.extra"])
        self.assertEqual(catalog.sources["test.extra"], "override")

    def test_override_revision_differs(self):
        with tempfile.TemporaryDirectory() as bundled_tmp, \
                tempfile.TemporaryDirectory() as override_tmp:
            bundled, overrides = Path(bundled_tmp), Path(override_tmp)
            self.prepare(bundled, {})
            plain = ProfileCatalog(str(bundled), "")
            (overrides / "base.yaml").write_text(
                json.dumps(minimal("test.base", version="2")),
                encoding="utf-8")
            overridden = ProfileCatalog(str(bundled), str(overrides))

        self.assertNotEqual(plain.revision, overridden.revision)

    def test_duplicate_override_is_rejected(self):
        with tempfile.TemporaryDirectory() as bundled_tmp, \
                tempfile.TemporaryDirectory() as override_tmp:
            bundled, overrides = Path(bundled_tmp), Path(override_tmp)
            self.prepare(bundled, {})
            (overrides / "a.yaml").write_text(
                json.dumps(minimal("test.base", version="2")),
                encoding="utf-8")
            (overrides / "b.yaml").write_text(
                json.dumps(minimal("test.base", version="3")),
                encoding="utf-8")

            catalog = ProfileCatalog(str(bundled), str(overrides))

        self.assertEqual(len(catalog.errors), 1)
        self.assertIn("duplicate profile id", catalog.errors[0]["error"])

    def test_dropping_an_override_reloads_on_next_access(self):
        with tempfile.TemporaryDirectory() as bundled_tmp, \
                tempfile.TemporaryDirectory() as override_tmp:
            bundled, overrides = Path(bundled_tmp), Path(override_tmp)
            self.prepare(bundled, {})
            profiles_module._catalog = None
            profiles_module._override_signature = ()
            try:
                with patch.object(
                        profiles_module, "_DEFAULT_DIR", str(bundled)), \
                        patch.object(
                            profiles_module, "_DEFAULT_OVERRIDES",
                            str(overrides)):
                    first = profiles_module.get_catalog()
                    (overrides / "base.yaml").write_text(
                        json.dumps({**minimal("test.base", version="2"),
                                    "x-note": "changed"}),
                        encoding="utf-8")
                    second = profiles_module.get_catalog()
            finally:
                profiles_module._catalog = None
                profiles_module._override_signature = ()

        self.assertNotEqual(first.revision, second.revision)
        self.assertEqual(second.sources["test.base"], "override")

    def test_diff_reports_added_removed_and_changed(self):
        diff = diff_profiles(
            {"a": "1", "b": "2", "c": "3"},
            {"a": "1", "b": "9", "d": "4"})

        self.assertEqual(diff, {
            "added": ["d"], "removed": ["c"], "changed": ["b"]})


if __name__ == "__main__":
    unittest.main()
