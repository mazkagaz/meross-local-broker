# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Tests for requesting and caching Appliance.System.Ability."""
import hashlib
import json
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

import broker_agent
from compat import OnlineStatus
from time_utils import utcnow

MQTT_KEY = "0123456789abcdef0123456789abcdef"
DEVICE_UUID = "aabbccddeeff00112233445566778899"
USER_ID = 7


class FakeMqttClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload):
        self.published.append((topic, json.loads(payload)))


class FakeDbHelper:
    def __init__(self, devices, abilities=None):
        self.devices = list(devices)
        self.abilities = dict(abilities or {})
        self.stored_abilities = []
        self.channels = []

    def get_all_devices(self):
        return list(self.devices)

    def get_device_by_uuid(self, device_uuid):
        for device in self.devices:
            if device.uuid == device_uuid:
                return device
        return None

    def get_device_ability(self, device_uuid):
        return self.abilities.get(device_uuid)

    def set_device_ability(self, device_uuid, ability):
        self.stored_abilities.append(ability)

    def update_device_channel(self, device_uuid, channel_id):
        self.channels.append((device_uuid, channel_id))


def make_broker():
    broker = broker_agent.Broker(
        hostname="localhost", port=2001, username="u", password="p",
        cert_ca=None, enable_bridging=False, device_timezone=None)
    broker.c = FakeMqttClient()
    return broker


def make_device(owner=True, online=True):
    return SimpleNamespace(
        uuid=DEVICE_UUID,
        online_status=(OnlineStatus.ONLINE if online
                       else OnlineStatus.OFFLINE),
        owner_user=(SimpleNamespace(user_id=USER_ID, mqtt_key=MQTT_KEY)
                    if owner else None),
    )


def ability_messages(broker):
    return [
        (topic, message) for topic, message in broker.c.published
        if message["header"]["namespace"] == "Appliance.System.Ability"
    ]


def ability_getack(abilities):
    return {
        "header": {
            "namespace": "Appliance.System.Ability",
            "method": "GETACK",
            "from": f"/appliance/{DEVICE_UUID}/publish",
        },
        "payload": {"ability": abilities},
    }


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
                updated_at=utcnow(),
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
                updated_at=utcnow(), ability_json="{}")},
        )
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._issue_devices_discovery()
        self.assertEqual(len(ability_messages(broker)), 1)

    def test_stale_ability_is_refreshed(self):
        broker = make_broker()
        db = FakeDbHelper(
            [make_device()],
            {DEVICE_UUID: SimpleNamespace(
                updated_at=utcnow() - timedelta(days=2),
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

    def test_offline_device_is_not_requested(self):
        broker = make_broker()
        db = FakeDbHelper([make_device(online=False)])
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._issue_devices_discovery()
        self.assertEqual(ability_messages(broker), [])
        self.assertNotIn(DEVICE_UUID, broker._ability_request_ts)

    def test_disconnect_clears_the_retry_cooldown(self):
        broker = make_broker()
        broker._ability_request_ts[DEVICE_UUID] = 1.0

        def get_device(device_uuid=None, **_kwargs):
            return make_device()

        def update_status(**_kwargs):
            return None

        db = SimpleNamespace(
            get_device_by_uuid=get_device,
            update_device_status=update_status)
        payload = {"event": "disconnect", "data": {
            "client_id": f"fmware:{DEVICE_UUID}_abc",
            "username": "u", "address": "a", "reason": 0}}
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_device_disconnected(payload)
        self.assertNotIn(DEVICE_UUID, broker._ability_request_ts)

    def test_stale_refresh_loop_requests_ability(self):
        broker = make_broker()
        db = FakeDbHelper([make_device()])
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker.refresh_stale_devices()
        self.assertEqual(len(ability_messages(broker)), 1)

    def test_agent_topic_ability_getack_is_stored(self):
        broker = make_broker()
        db = FakeDbHelper([make_device()])
        payload = ability_getack({
            "Appliance.System.All": {},
            "Appliance.RollerShutter.State": {},
        })
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_message_to_agent("/_agent", payload)

        self.assertEqual(len(db.stored_abilities), 1)
        self.assertIn("Appliance.RollerShutter.State",
                      db.stored_abilities[0])
        self.assertEqual(db.channels, [(DEVICE_UUID, 0)])

    def test_agent_topic_empty_ability_is_ignored(self):
        broker = make_broker()
        db = FakeDbHelper([make_device()])
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_message_to_agent("/_agent", ability_getack({}))
        self.assertEqual(db.stored_abilities, [])

    def test_agent_topic_ability_without_device_origin_is_ignored(self):
        broker = make_broker()
        db = FakeDbHelper([make_device()])
        payload = ability_getack({"Appliance.System.All": {}})
        payload["header"]["from"] = "/_agent"
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_message_to_agent("/_agent", payload)
        self.assertEqual(db.stored_abilities, [])


if __name__ == "__main__":
    unittest.main()
