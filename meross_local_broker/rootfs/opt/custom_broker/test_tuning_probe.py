# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Unit tests for the read-only live GET probe (no network)."""
from __future__ import annotations

import json
import re
import unittest
from hashlib import md5
from types import SimpleNamespace
from unittest.mock import patch

from tuning import MqttProbe, TuningTimeout, TuningUnavailable

UUID = "0123456789abcdef0123456789abcdef"
USER = SimpleNamespace(user_id=7, mqtt_key="secret")


class FakeClient:
    instances = []
    answer = True
    malformed = False
    connect_error = None
    connect_rc = 0
    response_method = "GETACK"
    response_payload = {"position": [{"channel": 0, "position": 42}]}

    def __init__(self, client_id, clean_session, protocol, transport):
        self.client_id = client_id
        self.subscribed = []
        self.published = []
        self.on_connect = None
        self.on_message = None
        self.username = None
        self.password = None
        self.disconnected = False
        self.stopped = False
        FakeClient.instances.append(self)

    def username_pw_set(self, username, password=None):
        self.username = username
        self.password = password

    def tls_set_context(self, context):
        self.context = context

    def connect(self, host, port, keepalive=60):
        if self.connect_error is not None:
            raise self.connect_error
        self.host = host
        self.port = port

    def loop_start(self):
        if self.on_connect is not None:
            self.on_connect(self, None, None, self.connect_rc)

    def subscribe(self, topic, qos=0):
        self.subscribed.append((topic, qos))

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))
        if self.malformed:
            self.on_message(self, None, SimpleNamespace(
                payload=b"{not json"))
            return
        if not self.answer:
            return
        request = json.loads(payload)
        header = request["header"]
        response = {
            "header": {
                "messageId": header["messageId"],
                "namespace": header["namespace"],
                "method": self.response_method,
                "from": f"/appliance/{UUID}/publish",
                "sign": "deadbeef",
            },
            "payload": self.response_payload,
        }
        self.on_message(self, None, SimpleNamespace(
            payload=json.dumps(response).encode()))

    def disconnect(self):
        self.disconnected = True

    def loop_stop(self):
        self.stopped = True


class MqttProbeTest(unittest.TestCase):
    def setUp(self):
        FakeClient.instances = []
        FakeClient.answer = True
        FakeClient.malformed = False
        FakeClient.connect_error = None
        FakeClient.connect_rc = 0
        FakeClient.response_method = "GETACK"
        FakeClient.response_payload = {
            "position": [{"channel": 0, "position": 42}]}
        patchers = [
            patch("tuning.mqtt.Client", FakeClient),
            patch("tuning.ssl.create_default_context",
                  lambda cafile=None: SimpleNamespace(
                      check_hostname=True, verify_mode=None)),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.probe = MqttProbe(host="127.0.0.1", port=2001, ca="ca.pem")

    def test_read_publishes_signed_get_and_returns_values(self):
        result = self.probe.read(
            UUID, USER, "Appliance.RollerShutter.Position", {}, 2)

        client = FakeClient.instances[0]
        self.assertRegex(client.client_id, r"^app:7_tuning[0-9a-f]{8}$")
        self.assertEqual(client.username, "7")
        self.assertEqual(client.password,
                         md5(b"7secret").hexdigest())
        self.assertEqual(len(client.subscribed), 1)
        self.assertEqual(len(client.published), 1)

        topic, payload, _qos = client.published[0]
        self.assertEqual(topic, f"/appliance/{UUID}/subscribe")
        request = json.loads(payload)
        header = request["header"]
        self.assertEqual(header["method"], "GET")
        self.assertEqual(
            header["namespace"], "Appliance.RollerShutter.Position")
        self.assertEqual(header["from"], client.subscribed[0][0])
        self.assertRegex(client.subscribed[0][0],
                         r"^/app/7-tuning[0-9a-f]{8}/subscribe$")
        self.assertTrue(header["sign"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["method"], "GETACK")
        self.assertEqual(result["payload"], {
            "position": [{"channel": 0, "position": 42}]})
        self.assertNotIn("sign", result["header"])
        self.assertNotIn("messageId", result["header"])
        self.assertTrue(client.disconnected)
        self.assertTrue(client.stopped)

    def test_send_uses_the_requested_method(self):
        payload = {"position": [{"channel": 0, "position": 42}]}
        result = self.probe.send(
            UUID, USER, "SET", "Appliance.RollerShutter.Position",
            payload, 2)
        client = FakeClient.instances[0]
        request = json.loads(client.published[0][1])
        self.assertEqual(request["header"]["method"], "SET")
        self.assertEqual(request["payload"], payload)
        self.assertTrue(result["ok"])

    def test_device_error_is_reported_not_raised(self):
        FakeClient.response_method = "ERROR"
        FakeClient.response_payload = {}
        result = self.probe.read(UUID, USER, "Appliance.Test", {}, 2)
        self.assertFalse(result["ok"])
        self.assertEqual(result["method"], "ERROR")

    def test_timeout(self):
        FakeClient.answer = False
        with self.assertRaises(TuningTimeout):
            self.probe.read(UUID, USER, "Appliance.Test", {}, 0.01)

    def test_malformed_response_times_out(self):
        FakeClient.malformed = True
        with self.assertRaises(TuningTimeout):
            self.probe.read(UUID, USER, "Appliance.Test", {}, 0.01)

    def test_broker_unreachable(self):
        FakeClient.connect_error = OSError("refused")
        with self.assertRaises(TuningUnavailable):
            self.probe.read(UUID, USER, "Appliance.Test", {}, 1)

    def test_broker_rejects_connection(self):
        FakeClient.connect_rc = 5
        probe = MqttProbe(
            host="127.0.0.1", port=2001, ca="ca.pem",
            connect_timeout=0.01)
        with self.assertRaises(TuningUnavailable):
            probe.read(UUID, USER, "Appliance.Test", {}, 1)


if __name__ == "__main__":
    unittest.main()
