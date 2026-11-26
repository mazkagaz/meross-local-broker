# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Unit tests for the tuning store (V1)."""
from __future__ import annotations

import json
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from compat import OnlineStatus
from profiles import ProfileCatalog
from tuning import (
    MAX_YAML_BYTES,
    TuningConflict,
    TuningError,
    TuningNotFound,
    TuningRateLimited,
    TuningStore,
    TuningTimeout,
)

PROFILES = Path(__file__).with_name("device_profiles")
UUID = "0123456789abcdef0123456789abcdef"


class FakeProbe:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.sends = []
        self.result = result or {
            "ok": True, "method": "GETACK", "payload": {}}
        self.error = error

    def _invoke(self):
        if self.error is not None:
            raise self.error
        return dict(self.result)

    def read(self, uuid, user, namespace, payload, timeout):
        self.calls.append((uuid, namespace, payload, timeout))
        return self._invoke()

    def send(self, uuid, user, method, namespace, payload, timeout):
        self.sends.append((uuid, method, namespace, payload, timeout))
        return self._invoke()


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

    def _install_device(self, device_type="mss425", online=True,
                        channels=(0, 1), abilities=(), subdevices=()):
        device = SimpleNamespace(
            uuid=UUID,
            mac="AABBCCDDEEFF",
            dev_name="Test device",
            device_type=device_type,
            sub_type=None,
            online_status=(OnlineStatus.ONLINE if online
                           else OnlineStatus.OFFLINE),
            channels=[SimpleNamespace(channel_id=c) for c in channels],
            child_subdevices=[
                SimpleNamespace(sub_device_id=i, sub_device_type=t,
                                sub_device_name=n)
                for i, t, n in subdevices],
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
        self.store._statuses = lambda uuid: [SimpleNamespace(
            channel=0, position=42, state=1,
            updated_at=datetime(2026, 11, 22, 10, 1, tzinfo=timezone.utc))]
        self.store._configs = lambda uuid: []
        self.store._adjusts = lambda uuid: []
        return device

    def test_device_state_reports_entities_and_cache(self):
        self._install_device(abilities=["Appliance.Control.ToggleX"])
        state = self.store.device_state(UUID)

        self.assertEqual(state["profile"]["id"], "meross.mss425")
        self.assertEqual(
            {entity["key"] for entity in state["entities"]},
            {"outlet_0", "outlet_1"})
        self.assertEqual(state["device"]["channels"], [0, 1])
        self.assertIn("Appliance.Control.ToggleX", state["ability"])
        self.assertEqual(
            state["cache"]["roller_shutter"]["status"][0]["position"], 42)
        polling = {row["namespace"]: row for row in state["polling"]}
        self.assertIn("GET", polling["Appliance.Control.ToggleX"]["methods"])

        with self.assertRaises(TuningNotFound):
            self.store.device_state("missing")

    def test_simulate_extracts_values_for_all_payload_channels(self):
        result = self.store.simulate(
            "meross.mss425", "Appliance.Control.ToggleX", "PUSH",
            {"togglex": [{"channel": 0, "onoff": 1},
                         {"channel": 1, "onoff": 0}]})
        self.assertTrue(result["known_namespace"])
        self.assertEqual(result["applied"], 2)
        self.assertEqual(result["entities"]["outlet_0"], {"onoff": 1})
        self.assertEqual(result["entities"]["outlet_1"], {"onoff": 0})

        result = self.store.simulate(
            "meross.mrs100", "Appliance.RollerShutter.Position", "PUSH",
            {"position": [{"channel": 0, "position": 42}]})
        self.assertEqual(result["entities"]["cover"], {"position": 42})

    def test_simulate_subdevice_template(self):
        result = self.store.simulate(
            "meross.msh300", "Appliance.Hub.Sensor.TempHum", "GETACK",
            {"tempHum": [{"id": "sub1", "latestTemperature": 235}]},
            subdevice={"id": "sub1", "type": "ms1"})
        self.assertEqual(
            result["subdevices"]["sub1"]["temperature"], {"value": 23.5})

    def test_simulate_rejects_bad_requests(self):
        with self.assertRaises(TuningNotFound):
            self.store.simulate(
                "missing.profile", "Appliance.X", "PUSH", {})
        with self.assertRaises(TuningError):
            self.store.simulate(
                "meross.mrs100", "Appliance.RollerShutter.Position",
                "GET", {})
        with self.assertRaises(TuningError):
            self.store.simulate(
                "meross.msh300", "Appliance.Hub.Sensor.TempHum", "PUSH",
                {"tempHum": []}, subdevice={"id": "s", "type": "zzz"})
        with self.assertRaises(TuningError):
            self.store.simulate(
                "meross.mrs100", "Appliance.RollerShutter.Position",
                "PUSH", ["not", "an", "object"])
        with self.assertRaises(TuningError):
            self.store.simulate(
                "meross.mss425", "Appliance.Control.ToggleX", "PUSH",
                {}, channels="0")

        result = self.store.simulate(
            "meross.mrs100", "Appliance.Unknown", "PUSH", {})
        self.assertFalse(result["known_namespace"])
        self.assertTrue(result["warnings"])

        result = self.store.simulate(
            "meross.mss425", "Appliance.Control.ToggleX", "PUSH",
            {"togglex": [{"channel": 5, "onoff": 1}]}, channels=[0])
        self.assertEqual(result["applied"], 0)
        self.assertEqual(result["ignored"], 1)

    def test_read_device_uses_profile_namespace_and_rate_limits(self):
        self._install_device(abilities=["Appliance.Control.ToggleX"])
        probe = FakeProbe()
        self.store._probe = probe
        clock = SimpleNamespace(now=100.0)
        self.store._clock = lambda: clock.now

        result = self.store.read_device(UUID, timeout=3)
        self.assertEqual(result["profile_id"], "meross.mss425")
        self.assertEqual(probe.calls[0][1], "Appliance.Control.ToggleX")
        self.assertEqual(probe.calls[0][3], 3.0)

        with self.assertRaises(TuningRateLimited) as caught:
            self.store.read_device(UUID)
        self.assertGreaterEqual(caught.exception.retry_after, 1)

        clock.now += 5
        self.store.read_device(UUID, namespace="Appliance.System.All")
        self.assertEqual(probe.calls[1][1], "Appliance.System.All")

    def _install_mrs100(self, online=True):
        return self._install_device(
            device_type="mrs100", channels=(0,), online=online,
            abilities=["Appliance.RollerShutter.State"])

    def test_command_catalog_exposes_typed_commands(self):
        self._install_mrs100()
        catalog = self.store.device_commands(UUID)
        self.assertEqual(catalog["profile_id"], "meross.mrs100")
        by_id = {row["id"]: row for row in catalog["commands"]}
        position = by_id["cover.set_position"]
        self.assertEqual(position["type"], "number")
        self.assertEqual(position["channels"], [0])
        self.assertEqual(position["payload_template"], {
            "position": {"channel": "$channel", "position": "$value"}})
        duration = by_id["open_duration.set_value"]
        self.assertEqual(duration["min"], 10)
        self.assertEqual(duration["max"], 120)
        self.assertEqual(duration["value_scale"], 1000)
        self.assertEqual(by_id["start_calibration.press"]["type"],
                         "action")
        self.assertIn("Appliance.RollerShutter.Position",
                      catalog["namespaces"])

    def test_command_requires_confirmation_and_executes_once(self):
        self._install_mrs100()
        probe = FakeProbe(result={
            "ok": True, "method": "SETACK", "payload": {}})
        self.store._probe = probe
        clock = SimpleNamespace(now=100.0)
        self.store._clock = lambda: clock.now

        preview = self.store.execute_command(
            UUID, "cover.set_position", channel=0, value=42)
        self.assertTrue(preview["requires_confirmation"])
        self.assertEqual(preview["command"]["payload"],
                         {"position": {"channel": 0, "position": 42}})
        self.assertEqual(probe.sends, [])

        result = self.store.execute_command(
            UUID, "cover.set_position", confirm=True,
            token=preview["token"])
        self.assertTrue(result["ok"])
        self.assertEqual(probe.sends[0][1], "SET")
        self.assertEqual(probe.sends[0][2],
                         "Appliance.RollerShutter.Position")
        entries = self.store.audit_entries()
        self.assertEqual(entries[0]["action"], "device.command")
        self.assertEqual(entries[0]["device_uuid"], UUID)
        self.assertTrue(entries[0]["ok"])
        self.assertIn("before", entries[0])
        self.assertIn("after", entries[0])

        with self.assertRaises(TuningConflict):
            self.store.execute_command(
                UUID, "cover.set_position", confirm=True,
                token=preview["token"])

    def test_command_tokens_expire_and_bind_the_payload(self):
        self._install_mrs100()
        probe = FakeProbe()
        self.store._probe = probe
        clock = SimpleNamespace(now=100.0)
        self.store._clock = lambda: clock.now
        preview = self.store.execute_command(
            UUID, "open_duration.set_value", channel=0, value=12.5)
        self.assertEqual(preview["command"]["payload"],
                         {"config": {"channel": 0, "signalOpen": 12500}})

        clock.now += 2
        second = self.store.execute_command(
            UUID, "cover.open", channel=0)
        with self.assertRaises(TuningConflict):
            self.store.execute_command(
                UUID, "cover.set_position", confirm=True,
                token=second["token"])

        clock.now += 61
        with self.assertRaises(TuningConflict):
            self.store.execute_command(
                UUID, "cover.open", confirm=True, token=second["token"])
        self.assertEqual(probe.sends, [])

    def test_command_validates_target_and_values(self):
        self._install_mrs100()
        self.store._probe = FakeProbe()
        with self.assertRaises(TuningError):
            self.store.execute_command(
                UUID, "open_duration.set_value", channel=0, value=5)
        with self.assertRaises(TuningError):
            self.store.execute_command(
                UUID, "cover.open", channel=3)
        with self.assertRaises(TuningError):
            self.store.execute_command(UUID, "missing.command")
        with self.assertRaises(TuningError):
            self.store.execute_command(
                UUID, "cover.set_position", channel=0, value="42")

        self._install_mrs100(online=False)
        with self.assertRaises(TuningConflict):
            self.store.execute_command(UUID, "cover.open", channel=0)
        with self.assertRaises(TuningNotFound):
            self.store.execute_command(
                "missing", "cover.open", channel=0)

    def test_command_degrades_on_timeout_and_busy(self):
        self._install_mrs100()
        clock = SimpleNamespace(now=100.0)
        self.store._clock = lambda: clock.now
        preview = self.store.execute_command(
            UUID, "cover.open", channel=0)
        self.store._probe = FakeProbe(error=TuningTimeout("no answer"))
        with self.assertRaises(TuningTimeout):
            self.store.execute_command(
                UUID, "cover.open", confirm=True,
                token=preview["token"])
        entries = self.store.audit_entries()
        self.assertFalse(entries[0]["ok"])
        self.assertIn("no answer", entries[0]["error"])

        clock.now += 5
        self.store._probe = FakeProbe()
        preview = self.store.execute_command(UUID, "cover.open", channel=0)
        self.store._busy_devices.add(UUID)
        try:
            with self.assertRaises(TuningConflict):
                self.store.execute_command(
                    UUID, "cover.open", confirm=True,
                    token=preview["token"])
        finally:
            self.store._busy_devices.discard(UUID)

    def test_read_device_returns_typed_values(self):
        self._install_mrs100()
        self.store._probe = FakeProbe(result={
            "ok": True, "namespace": "Appliance.RollerShutter.Position",
            "method": "GETACK",
            "payload": {"position": [{"channel": 0, "position": 42}]}})
        result = self.store.read_device(
            UUID, namespace="Appliance.RollerShutter.Position")
        self.assertEqual(result["typed"]["entities"]["cover"],
                         {"position": 42})

    def test_refresh_ability_fetches_and_stores_the_document(self):
        self._install_mrs100()
        probe = FakeProbe(result={
            "ok": True, "method": "GETACK",
            "payload": {"ability": {
                "Appliance.RollerShutter.State": {},
                "Appliance.System.All": {}}}})
        self.store._probe = probe
        stored = []
        self.store._set_ability = lambda device_uuid, ability: stored.append(
            (device_uuid, ability))
        clock = SimpleNamespace(now=100.0)
        self.store._clock = lambda: clock.now

        result = self.store.refresh_ability(UUID)
        self.assertEqual(result["count"], 2)
        self.assertEqual(stored[0][0], UUID)
        self.assertIn("Appliance.RollerShutter.State", stored[0][1])
        self.assertEqual(probe.sends[0][1], "GET")
        self.assertEqual(probe.sends[0][2], "Appliance.System.Ability")
        entries = self.store.audit_entries()
        self.assertEqual(entries[0]["action"], "device.ability")

        with self.assertRaises(TuningRateLimited):
            self.store.refresh_ability(UUID)

    def test_refresh_ability_rejects_empty_or_error(self):
        self._install_mrs100()
        stored = []
        self.store._set_ability = lambda device_uuid, ability: stored.append(
            ability)
        clock = SimpleNamespace(now=100.0)
        self.store._clock = lambda: clock.now

        self.store._probe = FakeProbe(result={
            "ok": True, "method": "GETACK", "payload": {"ability": {}}})
        with self.assertRaises(TuningError):
            self.store.refresh_ability(UUID)
        self.assertEqual(stored, [])

        clock.now += 5
        self._install_mrs100(online=False)
        with self.assertRaises(TuningConflict):
            self.store.refresh_ability(UUID)

        clock.now += 5
        self._install_mrs100()
        self.store._probe = FakeProbe(result={
            "ok": False, "method": "ERROR", "payload": {}})
        with self.assertRaises(TuningError):
            self.store.refresh_ability(UUID)
        self.assertEqual(stored, [])

    def test_read_device_degrades_explicitly(self):
        self._install_device(abilities=["Appliance.Control.ToggleX"])
        self.store._probe = FakeProbe(error=TuningTimeout("no answer"))
        with self.assertRaises(TuningTimeout):
            self.store.read_device(UUID)

        self._install_device(online=False,
                             abilities=["Appliance.Control.ToggleX"])
        with self.assertRaises(TuningConflict):
            self.store.read_device(UUID)

        self._install_device(abilities=["Appliance.Control.ToggleX"])
        with self.assertRaises(TuningError):
            self.store.read_device(UUID, namespace="Appliance.Unknown")

        with self.assertRaises(TuningNotFound):
            self.store.read_device("missing")


if __name__ == "__main__":
    unittest.main()
