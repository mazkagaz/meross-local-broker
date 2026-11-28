"""Tests for the broker response to Appliance.System.Clock PUSH."""
import hashlib
import json
import time
import unittest
from types import SimpleNamespace

import broker_agent

DEVICE_UUID = "20072954362882251h5448e1e927d636"
DEVICE_KEY = "0123456789abcdef0123456789abcdef"


class FakeMqttClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload):
        self.published.append((topic, json.loads(payload)))


def make_broker():
    broker = broker_agent.Broker(
        hostname="localhost", port=2001, username="u", password="p",
        cert_ca=None, enable_bridging=False, device_timezone=None)
    broker.c = FakeMqttClient()
    return broker


def make_user():
    return SimpleNamespace(user_id=1, mqtt_key=DEVICE_KEY)


def clock_payload(timestamp):
    return {
        "header": {
            "namespace": "Appliance.System.Clock",
            "method": "PUSH",
            "from": f"/appliance/{DEVICE_UUID}/publish",
        },
        "payload": {"clock": {"timestamp": timestamp}},
    }


def clock_messages(broker):
    return [
        (topic, message) for topic, message in broker.c.published
        if message["header"]["namespace"] == "Appliance.System.Clock"
    ]


class ClockPushReplyTest(unittest.TestCase):
    def test_replies_to_boot_relative_timestamp(self):
        broker = make_broker()

        self.assertTrue(broker._reply_to_clock_push(
            DEVICE_UUID, clock_payload(5), make_user()))

        topic, message = clock_messages(broker)[0]
        self.assertEqual(topic, f"/appliance/{DEVICE_UUID}/subscribe")
        self.assertEqual(message["header"]["method"], "PUSH")
        self.assertEqual(message["header"]["namespace"],
                         "Appliance.System.Clock")
        self.assertEqual(message["header"]["from"], "/_agent")
        self.assertAlmostEqual(
            message["payload"]["clock"]["timestamp"], time.time(), delta=5)
        header = message["header"]
        expected = hashlib.md5(
            f"{header['messageId']}{DEVICE_KEY}{header['timestamp']}".encode()
        ).hexdigest()
        self.assertEqual(header["sign"], expected)

    def test_skips_a_current_timestamp(self):
        broker = make_broker()

        self.assertFalse(broker._reply_to_clock_push(
            DEVICE_UUID, clock_payload(int(time.time())), make_user()))
        self.assertEqual(clock_messages(broker), [])

    def test_skips_an_invalid_timestamp(self):
        broker = make_broker()

        self.assertFalse(broker._reply_to_clock_push(
            DEVICE_UUID, clock_payload("not-a-number"), make_user()))
        self.assertEqual(clock_messages(broker), [])
