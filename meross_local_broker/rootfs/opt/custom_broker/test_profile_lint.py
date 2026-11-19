# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Tests for the device profile linter.

Run with: python3 -m unittest test_profile_lint
"""

import json
import unittest
from pathlib import Path

from profile_lint import (
    DEFAULT_PROFILES,
    DEFAULT_SCHEMA,
    expand_paths,
    lint_documents,
    load_documents,
    load_schema,
)


def profile(profile_id="test.device", entities=None, **overrides):
    data = {
        "schema_version": 2,
        "profile": {"id": profile_id, "version": "1"},
        "match": {"type": ["test"]},
        "payloads": {
            "Appliance.Control.ToggleX": {"methods": ["GETACK", "PUSH"]},
        },
        "entities": entities or [{
            "key": "switch",
            "platform": "switch",
            "state": {
                "namespace": "Appliance.Control.ToggleX",
                "fields": {"onoff": "togglex[0].onoff"},
            },
        }],
    }
    data.update(overrides)
    return data


class ProfileLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_schema(DEFAULT_SCHEMA)

    def lint(self, *documents):
        return lint_documents(documents, self.validator)

    def test_bundled_profiles_are_clean(self):
        errors, warnings = lint_documents(
            load_documents(expand_paths([str(DEFAULT_PROFILES)])),
            self.validator)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_duplicate_entity_key_is_rejected(self):
        data = profile(entities=[
            {"key": "dup", "platform": "switch"},
            {"key": "dup", "platform": "switch"},
        ])
        errors, _ = self.lint(("a.yaml", data))
        self.assertTrue(any("duplicate entity key" in error for error in errors))

    def test_unknown_namespace_is_rejected(self):
        data = profile(entities=[{
            "key": "sensor",
            "platform": "sensor",
            "state": {"namespace": "Appliance.Unknown", "fields": {"value": "x"}},
        }])
        errors, _ = self.lint(("a.yaml", data))
        self.assertTrue(any("not declared in payloads" in error for error in errors))

    def test_duplicate_profile_id_is_rejected(self):
        errors, _ = self.lint(
            ("a.yaml", profile("test.same")),
            ("b.yaml", profile("test.same")),
        )
        self.assertTrue(any("duplicate profile id" in error for error in errors))

    def test_hub_with_subdevice_is_accepted(self):
        data = profile(
            "test.hub",
            match={"kind": "hub", "type": ["hub"]},
            subdevices=[{
                "match": {"type": ["sub"]},
                "entities": [{
                    "key": "temp",
                    "platform": "sensor",
                    "device": "subdevice",
                    "state": {
                        "namespace": "Appliance.Control.ToggleX",
                        "fields": {"value": "x"},
                    },
                }],
            }],
        )
        errors, _ = self.lint(("hub.yaml", data))
        self.assertEqual(errors, [])

    def test_subdevices_require_hub_kind(self):
        data = profile(
            "test.hub",
            subdevices=[{"match": {"type": ["sub"]}, "entities": [
                {"key": "temp", "platform": "sensor"}]}],
        )
        errors, _ = self.lint(("hub.yaml", data))
        self.assertTrue(any("match.kind hub" in error for error in errors))

    def test_schema_copies_are_identical(self):
        docs_schema = Path(__file__).resolve().parents[4] / "docs" / \
            "device-profiles.schema.json"
        if not docs_schema.exists():
            self.skipTest("documentation schema not present")
        self.assertEqual(
            json.loads(docs_schema.read_text(encoding="utf-8")),
            json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
