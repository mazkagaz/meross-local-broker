# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""API tests for the tuning blueprint (no Home Assistant runtime)."""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from flask import Flask

import blueprints.tuning as tuning_blueprint
from blueprints.tuning import tuning_blueprint as blueprint
from profiles import ProfileCatalog
from tuning import TuningStore

PROFILES = Path(__file__).with_name("device_profiles")


class TuningApiTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.overrides = root / "overrides"
        self.overrides.mkdir()

        def catalog():
            return ProfileCatalog(str(PROFILES), str(self.overrides))

        self.store = TuningStore(
            overrides=self.overrides,
            backups=root / "backups",
            audit=root / "audit.jsonl",
            catalog_getter=catalog,
            catalog_reloader=lambda: {"revision": catalog().revision},
            devices=lambda: [],
            ability=lambda uuid: None,
        )
        patcher = patch.object(
            tuning_blueprint, "get_tuning_store", lambda: self.store)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.app = Flask(__name__)
        self.app.register_blueprint(blueprint, url_prefix="/_admin_")
        self.client = self.app.test_client()

    def _yaml(self, profile_id="meross.mod"):
        return self.store.get_profile(profile_id)["bundled_yaml"] + \
            "# tuning\n"

    def test_inventory_and_profile_detail(self):
        response = self.client.get("/_admin_/profiles")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["revision"])
        self.assertIn("meross.mod", [item["id"] for item in body["profiles"]])

        response = self.client.get("/_admin_/profiles/meross.mod")
        self.assertEqual(response.status_code, 200)
        self.assertIn("schema_version", response.get_json()["yaml"])

        response = self.client.get("/_admin_/profiles/absent.profile")
        self.assertEqual(response.status_code, 404)

    def test_validate_endpoint_reports_errors(self):
        response = self.client.post(
            "/_admin_/profiles/validate", json={"yaml": self._yaml()})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["valid"])
        self.assertEqual(response.get_json()["diff_base"], "bundled")
        self.assertIn("+# tuning", response.get_json()["diff"])

        response = self.client.post(
            "/_admin_/profiles/validate", json={"yaml": "profile: [\n"})
        self.assertFalse(response.get_json()["valid"])
        self.assertTrue(response.get_json()["errors"])
        self.assertFalse(response.get_json()["diff"])

        response = self.client.post(
            "/_admin_/profiles/validate", json={})
        self.assertEqual(response.status_code, 400)

    def test_override_roundtrip_conflict_and_delete(self):
        current = self.store.get_profile("meross.mod")
        response = self.client.put(
            "/_admin_/profiles/meross.mod/override",
            json={"yaml": self._yaml(),
                  "expected_hash": current["catalog_hash"]})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()["override_hash"])

        response = self.client.get("/_admin_/profiles/meross.mod")
        self.assertEqual(response.get_json()["source"], "override")
        self.assertIn("+# tuning", response.get_json()["diff"])
        override_hash = response.get_json()["override_hash"]

        response = self.client.put(
            "/_admin_/profiles/meross.mod/override",
            json={"yaml": self._yaml(), "expected_hash": "0" * 64})
        self.assertEqual(response.status_code, 409)

        response = self.client.delete(
            "/_admin_/profiles/meross.mod/override",
            json={"expected_hash": override_hash})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get("/_admin_/profiles/meross.mod")
            .get_json()["source"], "bundled")

    def test_export_and_import(self):
        current = self.store.get_profile("meross.mod")
        self.client.put(
            "/_admin_/profiles/meross.mod/override",
            json={"yaml": self._yaml(),
                  "expected_hash": current["catalog_hash"]})

        response = self.client.get(
            "/_admin_/profiles/export?format=zip&source=overrides")
        self.assertEqual(response.status_code, 200)
        archive = zipfile.ZipFile(BytesIO(response.data))
        self.assertIn("meross.mod.yaml", archive.namelist())

        response = self.client.get(
            "/_admin_/profiles/export?format=yaml&id=meross.mod")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"schema_version", response.data)

        response = self.client.get(
            "/_admin_/profiles/export?format=yaml&source=overrides"
            "&id=meross.absent")
        self.assertEqual(response.status_code, 404)

        new_yaml = self._yaml().replace(
            "id: meross.mod", "id: meross.tuning-test", 1)
        response = self.client.post(
            "/_admin_/profiles/import?dry_run=false",
            json={"profiles": [
                {"id": "meross.tuning-test", "yaml": new_yaml}]})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertFalse(response.get_json()["dry_run"])
        self.assertEqual(
            self.client.get("/_admin_/profiles/meross.tuning-test")
            .status_code, 200)

    def test_zip_import_ignores_entry_paths(self):
        new_yaml = self._yaml().replace(
            "id: meross.mod", "id: meross.zip-test", 1)
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../meross.zip-test.yaml", new_yaml)

        response = self.client.post(
            "/_admin_/profiles/import?dry_run=false",
            data={"file": (BytesIO(buffer.getvalue()), "profiles.zip")},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(
            response.get_json()["profiles"][0]["filename"],
            "meross.zip-test.yaml")
        self.assertTrue(
            (self.overrides / "meross.zip-test.yaml").is_file())
        self.assertFalse(
            (Path(self.temporary.name) / "meross.zip-test.yaml").exists())

    def test_audit_and_backups_endpoints(self):
        current = self.store.get_profile("meross.mod")
        self.client.put(
            "/_admin_/profiles/meross.mod/override",
            json={"yaml": self._yaml(),
                  "expected_hash": current["catalog_hash"]})
        response = self.client.get("/_admin_/tuning/audit")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["action"], "override.save")

        response = self.client.get(
            "/_admin_/profiles/meross.mod/backups")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
