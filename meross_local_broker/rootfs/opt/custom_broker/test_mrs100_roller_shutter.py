# Copyright (c) 2026 the MRS100 fork contributors.
# Licensed under the Apache License, Version 2.0. See NOTICE.
# Part of the MRS100 fork of ha-meross-local-broker.

"""Tests for MRS100 roller-shutter support in the local broker agent.

Run with: python3 -m unittest test_mrs100_roller_shutter
Requires the agent runtime dependencies (paho-mqtt, expiringdict, SQLAlchemy,
meross_iot).
"""
import json
import unittest
from types import SimpleNamespace
from unittest import mock

import broker_agent

DEVICE_UUID = "mrs10000000000000000000000000001"
DEVICE_KEY = "7b9ebd3edc1f13c6cb3f0d70d4ce066f"


class FakeMqttClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload):
        self.published.append((topic, json.loads(payload)))


class FakeDbHelper:
    def __init__(self):
        self.device = SimpleNamespace(
            uuid=DEVICE_UUID, device_type="mrs100", sub_type="eu",
            fmware_version="8.3.7", hdware_version="7.0.0", channels=[],
            owner_user=SimpleNamespace(mqtt_key=DEVICE_KEY, user_id=42),
            child_subdevices=[], local_ip="10.0.0.9",
            domain="homeassistant.local:2001", online_status=None)
        self.channels = set()
        self.configs = {}
        self.statuses = {}
        self.adjusts = {}
        self.ability = None

    def get_device_by_uuid(self, device_uuid):
        return self.device if device_uuid == DEVICE_UUID else None

    def get_all_devices(self):
        return [self.device]

    def find_user_owner_by_device_uuid(self, device_uuid):
        return self.device.owner_user if device_uuid == DEVICE_UUID else None

    def update_device(self, device):
        return device

    def update_device_status(self, device_uuid, status):
        return None

    def update_device_channel(self, device_uuid, channel_id):
        self.channels.add(channel_id)
        return None

    def set_roller_shutter_config(self, device_uuid, config):
        self.configs[int(config.get("channel", 0) or 0)] = dict(config)

    def get_roller_shutter_configs(self, device_uuid):
        return [SimpleNamespace(channel=ch, signal_open=cfg.get("signalOpen"),
                                signal_close=cfg.get("signalClose"),
                                payload_json=json.dumps(cfg))
                for ch, cfg in self.configs.items()]

    def set_device_ability(self, device_uuid, ability):
        self.ability = ability

    def get_device_ability(self, device_uuid):
        if self.ability is None:
            return None
        return SimpleNamespace(ability_json=json.dumps(self.ability))

    def set_roller_shutter_status(self, device_uuid, payload):
        for key in ("position", "state"):
            data = payload.get(key)
            entries = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                channel = int(entry.get("channel", 0) or 0)
                row = self.statuses.setdefault(channel, {"position": None, "state": None})
                if "position" in entry:
                    row["position"] = entry["position"]
                if "state" in entry:
                    row["state"] = entry["state"]

    def get_roller_shutter_statuses(self, device_uuid):
        return [SimpleNamespace(channel=ch, position=row["position"], state=row["state"])
                for ch, row in self.statuses.items()]

    def set_roller_shutter_adjust(self, device_uuid, payload):
        data = payload.get("adjust") or payload.get("adjust_results") or []
        entries = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        if not entries and "channel" in payload:
            entries = [payload]
        for entry in entries:
            if isinstance(entry, dict):
                self.adjusts[int(entry.get("channel", 0) or 0)] = dict(entry)

    def get_roller_shutter_adjusts(self, device_uuid):
        return [SimpleNamespace(channel=ch, payload_json=json.dumps(entry))
                for ch, entry in self.adjusts.items()]


def make_broker():
    broker = broker_agent.Broker(hostname="localhost", port=2001, username="u",
                                 password="p", cert_ca="/etc/ssl/certs/ca-certificates.crt",
                                 enable_bridging=False)
    broker.c = FakeMqttClient()
    return broker


def config_set(signal_open=25000, signal_close=30000, source="/app/1/subscribe"):
    return {
        "header": {"namespace": "Appliance.RollerShutter.Config", "method": "SET",
                   "from": source},
        "payload": {"config": {"channel": 0, "signalOpen": signal_open,
                               "signalClose": signal_close}},
    }


def system_all_getack():
    return {
        "header": {"namespace": "Appliance.System.All", "method": "GETACK",
                   "from": "/appliance/%s/publish" % DEVICE_UUID},
        "payload": {"all": {
            "system": {
                "hardware": {"type": "mrs100", "subType": "eu", "version": "7.0.0"},
                "firmware": {"version": "8.3.7", "server": "homeassistant.local",
                             "port": 2001, "innerIp": "10.0.0.9"},
                "time": {"timestamp": 1788556880, "timezone": "UTC", "timeRule": []},
                "online": {"status": 1},
            },
            "digest": {},  # MRS100 has no togglex entry
        }},
    }


class Mrs100RollerShutterTest(unittest.TestCase):
    def test_app_config_set_is_persisted(self):
        db = FakeDbHelper()
        broker = make_broker()
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_message("/appliance/%s/subscribe" % DEVICE_UUID,
                                   json.dumps(config_set()).encode())
        self.assertEqual(db.configs[0]["signalOpen"], 25000)
        self.assertEqual(db.configs[0]["signalClose"], 30000)

    def test_agent_config_replay_is_not_persisted(self):
        db = FakeDbHelper()
        broker = make_broker()
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_message("/appliance/%s/subscribe" % DEVICE_UUID,
                                   json.dumps(config_set(source="/_agent")).encode())
        self.assertEqual(db.configs, {})

    def test_system_all_creates_cover_channel_and_reapplies_config(self):
        db = FakeDbHelper()
        db.set_roller_shutter_config(DEVICE_UUID, config_set()["payload"]["config"])
        broker = make_broker()
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_message_to_agent("/_agent", system_all_getack())

        self.assertIn(0, db.channels)
        replayed = [(topic, msg) for topic, msg in broker.c.published
                    if msg["header"]["namespace"] == "Appliance.RollerShutter.Config"
                    and msg["header"]["method"] == "SET"]
        self.assertEqual(len(replayed), 1)
        topic, msg = replayed[0]
        self.assertEqual(topic, "/appliance/%s/subscribe" % DEVICE_UUID)
        self.assertEqual(msg["payload"]["config"]["signalOpen"], 25000)
        self.assertEqual(msg["header"]["from"], "/_agent")

    def test_ability_creates_cover_channel(self):
        db = FakeDbHelper()
        broker = make_broker()
        payload = {
            "header": {"namespace": "Appliance.System.Ability", "method": "GETACK"},
            "payload": {"ability": {"Appliance.RollerShutter.State": {}}},
        }
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_device_publication(
                DEVICE_UUID, "/appliance/%s/publish" % DEVICE_UUID, payload)
        self.assertIn(0, db.channels)
        self.assertEqual(db.ability, {"Appliance.RollerShutter.State": {}})

    def test_position_and_state_are_cached(self):
        db = FakeDbHelper()
        broker = make_broker()
        payload = {
            "header": {"namespace": "Appliance.RollerShutter.Position",
                       "method": "GETACK"},
            "payload": {"position": [{"channel": 0, "position": 42, "state": 1}]},
        }
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_device_publication(
                DEVICE_UUID, "/appliance/%s/publish" % DEVICE_UUID, payload)
        self.assertEqual(db.statuses[0]["position"], 42)
        self.assertEqual(db.statuses[0]["state"], 1)

    def test_devlist_exposes_ability_and_roller_metrics(self):
        from blueprints import device as device_api
        db = FakeDbHelper()
        db.set_device_ability(DEVICE_UUID, {"Appliance.RollerShutter.State": {}})
        db.set_roller_shutter_config(DEVICE_UUID,
                                     {"channel": 0, "signalOpen": 25000, "signalClose": 30000})
        db.set_roller_shutter_status(DEVICE_UUID,
                                     {"position": [{"channel": 0, "position": 42, "state": 1}]})
        db.set_roller_shutter_adjust(DEVICE_UUID,
                                     {"adjust": [{"channel": 0, "adjusted": 1,
                                                  "open_time": 25000,
                                                  "close_time": 30000}]})
        fake_device = SimpleNamespace(
            uuid=DEVICE_UUID,
            serialize=lambda: {"uuid": DEVICE_UUID, "deviceType": "mrs100"})
        with mock.patch.object(device_api, "dbhelper", db):
            item = device_api.serialize_device_metadata(fake_device)
        self.assertEqual(item["ability"], {"Appliance.RollerShutter.State": {}})
        self.assertEqual(item["rollerShutter"]["position"][0]["position"], 42)
        self.assertEqual(item["rollerShutter"]["adjust"][0]["open_time"], 25000)
        self.assertEqual(item["rollerShutter"]["config"][0]["signalOpen"], 25000)

    def test_adjust_results_are_cached(self):
        db = FakeDbHelper()
        broker = make_broker()
        payload = {
            "header": {"namespace": "Appliance.RollerShutter.Adjust",
                       "method": "GETACK"},
            "payload": {"adjust": [{"channel": 0, "adjusted": 1,
                                    "open_time": 25000, "close_time": 30000,
                                    "autoAdjust": 0}]},
        }
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_device_publication(
                DEVICE_UUID, "/appliance/%s/publish" % DEVICE_UUID, payload)
        self.assertEqual(db.adjusts[0]["open_time"], 25000)
        self.assertEqual(db.adjusts[0]["adjusted"], 1)


if __name__ == "__main__":
    unittest.main()
