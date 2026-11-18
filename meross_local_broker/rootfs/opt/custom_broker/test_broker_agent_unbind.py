"""Tests for the Appliance.Control.Unbind publication after a device forget.

Run with: python3 -m unittest test_broker_agent_unbind
(requires the agent runtime dependencies: paho-mqtt, expiringdict, SQLAlchemy, meross_iot)
"""
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest import mock

import broker_agent

USER_ID = 1
MQTT_KEY = "0123456789abcdef0123456789abcdef"
DEVICE_UUID = "aabbccddeeff00112233445566778899"


class FakeMqttClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload):
        self.published.append((topic, json.loads(payload)))


class FakeDbHelper:
    def __init__(self, pending, user):
        self.pending = pending
        self.user = user
        self.deleted = []

    def get_pending_unbinds(self):
        return list(self.pending)

    def get_user_by_id(self, user_id):
        return self.user if self.user is not None and user_id == self.user.user_id else None

    def delete_pending_unbind(self, device_uuid):
        self.deleted.append(device_uuid)
        self.pending = [p for p in self.pending if p.device_uuid != device_uuid]

    def get_all_devices(self):
        return []


def make_broker():
    broker = broker_agent.Broker(hostname="localhost", port=2001, username="u", password="p", cert_ca=None,
                                 enable_bridging=False, device_timezone=None)
    broker.c = FakeMqttClient()
    return broker


def pending_row(uuid=DEVICE_UUID, user_id=USER_ID):
    return SimpleNamespace(device_uuid=uuid, user_id=user_id)


class ProcessPendingUnbindsTest(unittest.TestCase):
    def test_publishes_signed_unbind_to_owner_app_topic(self):
        broker = make_broker()
        db = FakeDbHelper([pending_row()], SimpleNamespace(user_id=USER_ID, mqtt_key=MQTT_KEY))
        with mock.patch.object(broker_agent, "dbhelper", db):
            published = broker.process_pending_unbinds()

        self.assertEqual(published, [DEVICE_UUID])
        self.assertEqual(db.deleted, [DEVICE_UUID])
        self.assertEqual(len(broker.c.published), 1)
        topic, message = broker.c.published[0]
        self.assertEqual(topic, f"/app/{USER_ID}/subscribe")
        header = message["header"]
        self.assertEqual(header["method"], "PUSH")
        self.assertEqual(header["namespace"], "Appliance.Control.Unbind")
        self.assertEqual(header["from"], f"/appliance/{DEVICE_UUID}/publish")
        expected = hashlib.md5(
            f"{header['messageId']}{MQTT_KEY}{header['timestamp']}".encode()).hexdigest()
        self.assertEqual(header["sign"], expected)

    def test_drops_rows_whose_owner_is_gone_without_publishing(self):
        broker = make_broker()
        db = FakeDbHelper([pending_row()], None)
        with mock.patch.object(broker_agent, "dbhelper", db):
            published = broker.process_pending_unbinds()

        self.assertEqual(published, [])
        self.assertEqual(db.deleted, [DEVICE_UUID])
        self.assertEqual(broker.c.published, [])

    def test_each_pending_device_is_published_once(self):
        other_uuid = "11223344556677889900aabbccddeeff"
        broker = make_broker()
        db = FakeDbHelper([pending_row(), pending_row(uuid=other_uuid)],
                          SimpleNamespace(user_id=USER_ID, mqtt_key=MQTT_KEY))
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker.process_pending_unbinds()
            broker.process_pending_unbinds()

        self.assertEqual(db.deleted, [DEVICE_UUID, other_uuid])
        self.assertEqual([msg["header"]["from"] for _, msg in broker.c.published],
                         [f"/appliance/{DEVICE_UUID}/publish",
                          f"/appliance/{other_uuid}/publish"])

    def test_resubscribe_publishes_pending_unbinds(self):
        broker = make_broker()
        db = FakeDbHelper([pending_row()], SimpleNamespace(user_id=USER_ID, mqtt_key=MQTT_KEY))
        with mock.patch.object(broker_agent, "dbhelper", db), \
                mock.patch.object(broker, "_issue_devices_discovery") as discovery:
            broker._on_subscribe(None, None, None, None)

        discovery.assert_called_once_with()
        self.assertEqual(db.deleted, [DEVICE_UUID])
        self.assertEqual(len(broker.c.published), 1)


if __name__ == "__main__":
    unittest.main()
