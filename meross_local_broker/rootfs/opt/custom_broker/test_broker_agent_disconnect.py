"""Tests for $SYS/client-disconnections handling after a device forget.

Run with: python3 -m unittest test_broker_agent_disconnect
(requires the agent runtime dependencies: paho-mqtt, expiringdict, SQLAlchemy, meross_iot)
"""
import unittest
from types import SimpleNamespace
from unittest import mock

from meross_iot.model.enums import OnlineStatus

import broker_agent

DEVICE_UUID = "aabbccddeeff00112233445566778899"


class FakeDbHelper:
    def __init__(self, device):
        self.device = device
        self.status_calls = []

    def get_device_by_uuid(self, device_uuid):
        return self.device

    def update_device_status(self, device_uuid, status):
        self.status_calls.append((device_uuid, status))


def make_broker():
    broker = broker_agent.Broker(hostname="localhost", port=2001, username="u",
                                 password="p", cert_ca=None,
                                 enable_bridging=False, device_timezone=None)
    broker.c = SimpleNamespace(publish=lambda **kwargs: None)
    return broker


def disconnect_payload():
    return {
        "event": "disconnect",
        "data": {
            "client_id": f"fmware:{DEVICE_UUID}_0",
            "username": "AA:BB:CC:DD:EE:FF",
            "address": "10.0.0.9",
            "reason": "test",
        },
    }


class DeviceDisconnectTest(unittest.TestCase):
    def test_forgotten_device_disconnect_is_ignored(self):
        broker = make_broker()
        db = FakeDbHelper(device=None)
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_device_disconnected(disconnect_payload())

        self.assertEqual(db.status_calls, [])
        self.assertEqual(broker._devices_sys_info_timestamp, {})

    def test_known_device_disconnect_marks_it_offline(self):
        broker = make_broker()
        db = FakeDbHelper(device=SimpleNamespace(uuid=DEVICE_UUID))
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._handle_device_disconnected(disconnect_payload())

        self.assertEqual(
            db.status_calls, [(DEVICE_UUID, OnlineStatus.OFFLINE)])


if __name__ == "__main__":
    unittest.main()
