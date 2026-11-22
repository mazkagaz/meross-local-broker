# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Tests for requesting and caching Appliance.System.Ability."""
import hashlib
import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

import broker_agent

MQTT_KEY = "0123456789abcdef0123456789abcdef"
DEVICE_UUID = "aabbccddeeff00112233445566778899"


class FakeMqttClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload):
        self.published.append((topic, json.loads(payload)))


class FakeDbHelper:
    def __init__(self, devices, abilities=None):
        self.devices = list(devices)
        self.abilities = dict(abilities or {})

    def get_all_devices(self):
        return list(self.devices)

    def get_device_by_uuid(self, device_uuid):
        for device in self.devices:
            if device.uuid == device_uuid:
                return device
        return None

    def get_device_ability(self, device_uuid):
        return self.abilities.get(device_uuid)


def make_broker():
    broker = broker_agent.Broker(
        hostname="localhost", port=2001, username="u", password="p",
        cert_ca=None, enable_bridging=False, device_timezone=None)
    broker.c = FakeMqttClient()
    return broker


def make_device(owner=True):
    return SimpleNamespace(
        uuid=DEVICE_UUID,
        owner_user=(SimpleNamespace(mqtt_key=MQTT_KEY) if owner else None),
    )


def ability_messages(broker):
    return [
        (topic, message) for topic, message in broker.c.published
        if message["header"]["namespace"] == "Appliance.System.Ability"
    ]


class AbilityRequestTest(unittest.TestCase):
    def test_discovery_requests_missing_ability(self):
        broker = make_broker()
        db = FakeDbHelper([make_device()])
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._issue_devices_discovery()

        messages = ability_messages(broker)
        self.assertEqual(len(messages), 1)
        topic, message = messages[0]
        self.assertEqual(topic, f"/appliance/{DEVICE_UUID}/subscribe")
        header = message["header"]
        self.assertEqual(header["method"], "GET")
        self.assertEqual(header["namespace"], "Appliance.System.Ability")
        self.assertEqual(header["from"], "/_agent")
        expected = hashlib.md5(
            f"{header['messageId']}{MQTT_KEY}{header['timestamp']}".encode()
        ).hexdigest()
        self.assertEqual(header["sign"], expected)

    def test_recent_ability_is_not_requested(self):
        broker = make_broker()
        db = FakeDbHelper(
            [make_device()],
            {DEVICE_UUID: SimpleNamespace(
                updated_at=datetime.now(),
                ability_json='{"Appliance.System.All": {}}')},
        )
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._issue_devices_discovery()
        self.assertEqual(ability_messages(broker), [])

    def test_empty_ability_is_requested_again(self):
        broker = make_broker()
        db = FakeDbHelper(
            [make_device()],
            {DEVICE_UUID: SimpleNamespace(
                updated_at=datetime.now(), ability_json="{}")},
        )
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._issue_devices_discovery()
        self.assertEqual(len(ability_messages(broker)), 1)

    def test_stale_ability_is_refreshed(self):
        broker = make_broker()
        db = FakeDbHelper(
            [make_device()],
            {DEVICE_UUID: SimpleNamespace(
                updated_at=datetime.now() - timedelta(days=2),
                ability_json='{"Appliance.System.All": {}}')},
        )
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._issue_devices_discovery()
        self.assertEqual(len(ability_messages(broker)), 1)

    def test_cooldown_prevents_duplicate_requests(self):
        broker = make_broker()
        db = FakeDbHelper([make_device()])
        with mock.patch.object(broker_agent, "dbhelper", db):
            self.assertTrue(broker._maybe_request_ability(DEVICE_UUID))
            self.assertFalse(broker._maybe_request_ability(DEVICE_UUID))
        self.assertEqual(len(ability_messages(broker)), 1)

    def test_missing_owner_does_not_publish(self):
        broker = make_broker()
        db = FakeDbHelper([make_device(owner=False)])
        with mock.patch.object(broker_agent, "dbhelper", db):
            self.assertFalse(broker._issue_device_get_ability(DEVICE_UUID))
        self.assertEqual(broker.c.published, [])

    def test_stale_refresh_loop_requests_ability(self):
        broker = make_broker()
        db = FakeDbHelper([make_device()])
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker.refresh_stale_devices()
        self.assertEqual(len(ability_messages(broker)), 1)


if __name__ == "__main__":
    unittest.main()
