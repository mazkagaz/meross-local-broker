# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Unit tests for the tuning store (V1)."""
from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from profiles import ProfileCatalog
from tuning import (
    MAX_YAML_BYTES,
    TuningConflict,
    TuningError,
    TuningNotFound,
    TuningStore,
)

PROFILES = Path(__file__).with_name("device_profiles")


def profile_text(profile_id: str, version: str = "test") -> str:
    return f"""schema_version: 2
profile:
  id: {profile_id}
  version: "{version}"
  requires_engine: ">=2.2"
match:
  type: [testdev]
payloads:
  Appliance.Control.ToggleX:
    methods: [GETACK, PUSH]
    fields:
      togglex:
        type: array
        items:
          type: object
          fields:
            channel: {{ type: integer }}
            onoff: {{ type: integer }}
entities:
  - key: switch
    platform: switch
    channel: 0
    state:
      namespace: Appliance.Control.ToggleX
      channel: $channel
      fields: {{ onoff: "togglex[0].onoff" }}
"""


class TuningStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.overrides = root / "overrides"
        self.backups = root / "backups"
        self.audit = root / "audit.jsonl"
        self.overrides.mkdir()

        def catalog():
            return ProfileCatalog(str(PROFILES), str(self.overrides))

        self.store = TuningStore(
            overrides=self.overrides,
            backups=self.backups,
            audit=self.audit,
            catalog_getter=catalog,
            catalog_reloader=lambda: {"revision": catalog().revision},
            devices=lambda: [],
            ability=lambda uuid: None,
        )

    def test_validate_accepts_a_complete_profile(self):
        result = self.store.validate(profile_text("test.device"))

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.profile_id, "test.device")
        self.assertEqual(result.summary["entities"][0]["key"], "switch")
        self.assertEqual(result.diff_base, "none")
        self.assertIn("+profile:", result.diff)

    def test_validate_diff_tracks_bundled_then_override(self):
        base = self.store.get_profile("meross.mod")
        proposal = base["bundled_yaml"] + "# tuning\n"

        result = self.store.validate(
            proposal, profile_id="meross.mod")
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.diff_base, "bundled")
        self.assertIn("+# tuning", result.diff)

        self.store.save_override(
            "meross.mod", proposal, expected_hash=base["catalog_hash"])
        result = self.store.validate(
            proposal, profile_id="meross.mod")
        self.assertEqual(result.diff_base, "override")
        self.assertEqual(result.diff, "")

        second = proposal + "# tuning: second\n"
        result = self.store.validate(second, profile_id="meross.mod")
        self.assertIn("+# tuning: second", result.diff)

        profile = self.store.get_profile("meross.mod")
        self.assertIn("+# tuning", profile["diff"])

    def test_export_source_names(self):
        self.store.save_override("test.profile",
                                 profile_text("test.profile"))
        name, text = self.store.export_yaml(
            "test.profile", source="override")
        self.assertEqual(name, "test.profile.yaml")
        self.assertIn("profile:", text)

        _, effective = self.store.export_yaml(
            "test.profile", source="bundled")
        self.assertIn("profile:", effective)

        with self.assertRaises(TuningError):
            self.store.export_yaml("test.profile", source="bogus")
        with self.assertRaises(TuningNotFound):
            self.store.export_yaml("meross.mod", source="overrides")

    def test_rejects_oversized_profile_ids(self):
        long_id = "a" * 129
        with self.assertRaises(TuningError):
            self.store.save_override(long_id, profile_text(long_id))
        with self.assertRaises(TuningError):
            self.store.import_profiles([("long.yaml", profile_text(long_id))])
        with self.assertRaises(TuningError):
            self.store.export_yaml(long_id)
        self.assertFalse(any(self.overrides.iterdir()))

    def test_validate_reports_yaml_location_and_limits(self):
        result = self.store.validate("profile: [\n")
        self.assertFalse(result.valid)
        self.assertIn("line", result.errors[0])

        result = self.store.validate(
            "schema_version: 2\n" + "x" * MAX_YAML_BYTES)
        self.assertFalse(result.valid)
        self.assertIn("exceeds", result.errors[0])

        result = self.store.validate(profile_text("test.device"),
                                     profile_id="other.profile")
        self.assertFalse(result.valid)
        self.assertIn("does not match", result.errors[0])

    def test_validate_rejects_unknown_state_namespace(self):
        text = profile_text("test.device").replace(
            "Appliance.Control.ToggleX\n      channel",
            "Appliance.Unknown\n      channel", 1)
        result = self.store.validate(text)
        self.assertFalse(result.valid)

    def test_save_override_is_atomic_backed_up_and_audited(self):
        initial = self.store.validate(profile_text("test.profile"))
        self.assertTrue(initial.valid)
        self.store.save_override(
            "test.profile", profile_text("test.profile"))

        override = self.overrides / "test.profile.yaml"
        self.assertTrue(override.is_file())
        current = self.store.get_profile("test.profile")
        self.assertEqual(current["source"], "override")
        self.assertEqual(current["override_hash"],
                         current["override_hash"])

        saved = self.store.save_override(
            "test.profile", profile_text("test.profile", "2"),
            expected_hash=current["override_hash"])
        self.assertIn("@@", saved["diff"])
        backups = list(self.backups.glob("*-test.profile.yaml"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(stat.S_IMODE(override.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.audit.stat().st_mode), 0o600)
        entries = self.store.audit_entries()
        self.assertEqual(entries[0]["action"], "override.save")
        self.assertEqual(entries[0]["profile_id"], "test.profile")

    def test_failed_write_keeps_previous_override(self):
        self.store.save_override("test.profile",
                                 profile_text("test.profile"))
        override = self.overrides / "test.profile.yaml"
        before = override.read_text()
        with patch("tuning.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.save_override(
                    "test.profile", profile_text("test.profile", "2"))
        self.assertEqual(override.read_text(), before)
        self.assertFalse(list(self.overrides.glob(".test.profile.yaml.*")))
        self.assertEqual(
            self.store.get_profile("test.profile")["version"], "test")

    def test_conflict_does_not_write(self):
        self.store.save_override("test.profile",
                                 profile_text("test.profile"))
        before = (self.overrides / "test.profile.yaml").read_text()
        with self.assertRaises(TuningConflict):
            self.store.save_override(
                "test.profile", profile_text("test.profile", "2"),
                expected_hash="0" * 64)
        self.assertEqual(
            (self.overrides / "test.profile.yaml").read_text(), before)

    def test_delete_and_restore_backup(self):
        base = self.store.get_profile("meross.mod")
        first = base["bundled_yaml"] + "# tuning: first\n"
        second = base["bundled_yaml"] + "# tuning: second\n"
        self.store.save_override(
            "meross.mod", first, expected_hash=base["catalog_hash"])
        current = self.store.get_profile("meross.mod")
        self.store.save_override(
            "meross.mod", second, expected_hash=current["override_hash"])

        self.store.delete_override("meross.mod")
        self.assertEqual(self.store.get_profile(
            "meross.mod")["source"], "bundled")
        backup = self.store.list_backups("meross.mod")[0]["file"]
        self.store.restore_backup("meross.mod", backup)
        self.assertEqual(self.store.get_profile(
            "meross.mod")["source"], "override")

    def test_export_and_import(self):
        self.store.save_override("test.profile",
                                 profile_text("test.profile"))
        name, payload = self.store.export_zip()
        self.assertEqual(name, "meross-profiles.zip")
        self.assertIn(b"manifest.json", payload)

        imported = self.store.import_profiles(
            [("copy.yaml", profile_text("test.copy"))], dry_run=True)
        self.assertTrue(imported["dry_run"])
        self.assertFalse((self.overrides / "test.copy.yaml").exists())

        imported = self.store.import_profiles(
            [("copy.yaml", profile_text("test.copy"))], dry_run=False)
        self.assertFalse(imported["dry_run"])
        self.assertTrue((self.overrides / "test.copy.yaml").exists())

        with self.assertRaises(TuningError):
            self.store.import_profiles([
                ("a.yaml", profile_text("test.dup")),
                ("b.yaml", profile_text("test.dup")),
            ])

    def test_invalid_profile_never_reaches_disk(self):
        with self.assertRaises(TuningError):
            self.store.save_override("test.profile", "profile: [\n")
        self.assertFalse((self.overrides / "test.profile.yaml").exists())


if __name__ == "__main__":
    unittest.main()
