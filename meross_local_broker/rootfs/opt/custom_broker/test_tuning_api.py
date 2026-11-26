# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""API tests for the tuning blueprint (no Home Assistant runtime)."""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

import blueprints.tuning as tuning_blueprint
from blueprints.tuning import tuning_blueprint as blueprint
from capture import CaptureManager
from compat import OnlineStatus
from profiles import ProfileCatalog
from tuning import TuningStore

PROFILES = Path(__file__).with_name("device_profiles")
DEVICE_UUID = "0123456789abcdef0123456789abcdef"


class FakeProbe:
    def __init__(self, result=None):
        self.calls = []
        self.sends = []
        self.result = result

    def _invoke(self, default):
        return dict(self.result) if self.result is not None else default

    def read(self, uuid, user, namespace, payload, timeout):
        self.calls.append((uuid, namespace, payload, timeout))
        return self._invoke(
            {"ok": True, "method": "GETACK", "payload": {}})

    def send(self, uuid, user, method, namespace, payload, timeout):
        self.sends.append((uuid, method, namespace, payload, timeout))
        return self._invoke(
            {"ok": True, "method": "SETACK", "payload": {}})


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


    def _install_device(self, online=True, device_type="mss425",
                        channels=(0, 1),
                        abilities=("Appliance.Control.ToggleX",)):
        device = SimpleNamespace(
            uuid=DEVICE_UUID,
            mac="AABBCCDDEEFF",
            dev_name="Test device",
            device_type=device_type,
            sub_type=None,
            online_status=(OnlineStatus.ONLINE if online
                           else OnlineStatus.OFFLINE),
            channels=[SimpleNamespace(channel_id=channel)
                      for channel in channels],
            child_subdevices=[],
            local_ip="192.168.1.10",
            fmware_version="1.0.0",
            hdware_version="1.0",
            last_seen_time=datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc),
            owner_user=SimpleNamespace(user_id=7, mqtt_key="secret"),
        )
        self.store._devices = lambda: [device]
        self.store._ability = lambda uuid: SimpleNamespace(
            ability_json=json.dumps(
                {name: {} for name in abilities}))
        self.store._statuses = lambda uuid: []
        self.store._configs = lambda uuid: []
        self.store._adjusts = lambda uuid: []
        return device

    def _install_mrs100(self, online=True):
        return self._install_device(
            online=online, device_type="mrs100", channels=(0,),
            abilities=("Appliance.RollerShutter.State",))

    def test_device_state_endpoint(self):
        self._install_device()
        response = self.client.get(
            f"/_admin_/tuning/devices/{DEVICE_UUID}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["profile"]["id"], "meross.mss425")
        self.assertEqual(
            [item["key"] for item in response.get_json()["entities"]],
            ["outlet_0", "outlet_1"])
        self.assertTrue(
            response.get_json()["device"]["last_seen"].endswith("Z"))

        response = self.client.get("/_admin_/tuning/devices/missing")
        self.assertEqual(response.status_code, 404)

    def test_preview_endpoint(self):
        response = self.client.post(
            "/_admin_/profiles/meross.mrs100/preview",
            json={"namespace": "Appliance.RollerShutter.Position",
                  "method": "PUSH",
                  "payload": {"position": [
                      {"channel": 0, "position": 42}]}})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(
            response.get_json()["entities"]["cover"], {"position": 42})

        response = self.client.post(
            "/_admin_/profiles/meross.mrs100/preview",
            json={"namespace": "Appliance.RollerShutter.Position",
                  "method": "GET", "payload": {}})
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/_admin_/profiles/missing/preview", json={})
        self.assertEqual(response.status_code, 404)

    def test_read_endpoint_and_rate_limit(self):
        self._install_device()
        probe = FakeProbe()
        self.store._probe = probe

        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/read", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["profile_id"], "meross.mss425")

        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/read", json={})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

        self._install_device(online=False)
        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/read", json={})
        self.assertEqual(response.status_code, 409)

        response = self.client.post(
            "/_admin_/tuning/devices/missing/read", json={})
        self.assertEqual(response.status_code, 404)

    def test_read_endpoint_rejects_unknown_namespace(self):
        self._install_device()
        self.store._probe = FakeProbe()
        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/read",
            json={"namespace": "Appliance.Unknown"})
        self.assertEqual(response.status_code, 400)

    def test_command_endpoints_confirm_once(self):
        self._install_mrs100()
        probe = FakeProbe()
        self.store._probe = probe

        response = self.client.get(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/commands")
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.get_json()["commands"]]
        self.assertIn("cover.set_position", ids)

        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/commands/"
            "cover.set_position",
            json={"channel": 0, "value": 42})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()["requires_confirmation"])
        token = response.get_json()["token"]

        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/commands/"
            "cover.set_position",
            json={"confirm": True, "token": token})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()["ok"])
        self.assertEqual(probe.sends[0][3],
                         {"position": {"channel": 0, "position": 42}})

        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/commands/"
            "cover.set_position",
            json={"confirm": True, "token": token})
        self.assertEqual(response.status_code, 409)

        response = self.client.get(
            f"/_admin_/tuning/audit?device_uuid={DEVICE_UUID}")
        self.assertEqual(response.get_json()[0]["action"],
                         "device.command")

    def test_command_endpoint_degrades(self):
        self._install_mrs100()
        self.store._probe = FakeProbe()
        self.store._clock = lambda: 100.0

        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/commands/cover.open",
            json={"channel": 0})
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/commands/cover.open",
            json={"channel": 0})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/commands/unknown",
            json={})
        self.assertEqual(response.status_code, 400)

        self._install_mrs100(online=False)
        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/commands/cover.open",
            json={"channel": 0})
        self.assertEqual(response.status_code, 409)

    def test_ability_refresh_endpoint(self):
        self._install_mrs100()
        stored = []
        self.store._set_ability = lambda device_uuid, ability: stored.append(
            ability)
        self.store._probe = FakeProbe(result={
            "ok": True, "method": "GETACK",
            "payload": {"ability": {
                "Appliance.RollerShutter.State": {},
                "Appliance.System.All": {}}}})
        self.store._clock = lambda: 100.0

        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/ability", json={})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["count"], 2)
        self.assertIn("Appliance.RollerShutter.State",
                      response.get_json()["namespaces"])
        self.assertEqual(len(stored), 1)

        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/ability", json={})
        self.assertEqual(response.status_code, 429)

        self._install_mrs100(online=False)
        response = self.client.post(
            f"/_admin_/tuning/devices/{DEVICE_UUID}/ability", json={})
        self.assertEqual(response.status_code, 409)

        response = self.client.post(
            "/_admin_/tuning/devices/missing/ability", json={})
        self.assertEqual(response.status_code, 404)

    def test_capture_endpoints(self):
        manager = CaptureManager(str(Path(self.temporary.name) / "capture"))
        patcher = patch.object(
            tuning_blueprint, "get_capture_manager", lambda: manager)
        patcher.start()
        self.addCleanup(patcher.stop)

        response = self.client.post(
            "/_admin_/tuning/capture/start",
            json={"uuid": DEVICE_UUID, "type": "mrs100"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["active"])
        self.assertEqual(
            self.client.get("/_admin_/tuning/capture/status")
            .get_json()["frames"], 0)

        manager.record(DEVICE_UUID, "rx",
                       f"/appliance/{DEVICE_UUID}/publish",
                       {"header": {"namespace": "Appliance.Test",
                                   "method": "PUSH"},
                        "payload": {"value": 1}})
        response = self.client.post(
            "/_admin_/tuning/capture/draft", json={"type": "mrs100"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("schema_version: 2", response.get_json()["yaml"])

        response = self.client.get("/_admin_/tuning/capture/export")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        with zipfile.ZipFile(BytesIO(response.data)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"session.json", "frames.jsonl", "draft.yaml"})

        response = self.client.post("/_admin_/tuning/capture/stop")
        self.assertFalse(response.get_json()["active"])

    def test_capture_export_without_a_session(self):
        manager = CaptureManager(str(Path(self.temporary.name) / "empty"))
        patcher = patch.object(
            tuning_blueprint, "get_capture_manager", lambda: manager)
        patcher.start()
        self.addCleanup(patcher.stop)

        response = self.client.get("/_admin_/tuning/capture/export")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
