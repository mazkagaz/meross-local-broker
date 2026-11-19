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

from profiles import ProfileCatalog

HERE = Path(__file__).parent
PROFILES = HERE / "device_profiles"


class ProfileCatalogTest(unittest.TestCase):
    def test_bundled_catalog_is_valid_and_stable(self):
        first = ProfileCatalog(str(PROFILES))
        second = ProfileCatalog(str(PROFILES))

        self.assertEqual(first.errors, [])
        self.assertEqual(len(first.profiles), 3)
        self.assertEqual(first.revision, second.revision)
        self.assertEqual(len(first.revision), 64)
        self.assertIn("meross.mrs100", first.profiles)

    def test_revision_payload_and_catalog_shape(self):
        catalog = ProfileCatalog(str(PROFILES))

        revision = catalog.revision_payload()
        self.assertEqual(revision["schema_version"], 1)
        self.assertEqual(revision["count"], 3)
        self.assertEqual(revision["errors"], 0)

        payload = catalog.payload()
        self.assertEqual(payload["revision"], catalog.revision)
        ids = sorted(item["id"] for item in payload["profiles"])
        self.assertEqual(ids, ["meross.mrs100", "meross.msl120", "meross.mss310"])
        for item in payload["profiles"]:
            self.assertEqual(item["source"], "bundled")
            self.assertEqual(len(item["hash"]), 64)
            self.assertIn("profile", item)

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
        self.assertEqual(catalog.errors[0]["file"], "broken.yaml")


if __name__ == "__main__":
    unittest.main()
