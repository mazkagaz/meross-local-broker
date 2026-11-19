# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Tests for the device-to-app delivery topics.

Run with: python3 -m unittest test_broker_agent_forwarding
"""

import unittest
from types import SimpleNamespace
from unittest import mock

import broker_agent
from broker_agent import _app_forward_topics


def message(from_topic, method="GETACK", message_id="mid"):
    return {
        "header": {
            "from": from_topic, "method": method, "messageId": message_id},
        "payload": {},
    }


def request(from_topic, method="GET", message_id="mid"):
    return message(from_topic, method=method, message_id=message_id)


class AppForwardTopicsTest(unittest.TestCase):
    def test_push_goes_to_the_user_topic_only(self):
        self.assertEqual(
            _app_forward_topics(
                1, message("/appliance/uuid/publish", method="PUSH")),
            ["/app/1/subscribe"])

    def test_command_ack_follows_the_recorded_response_topic(self):
        self.assertEqual(
            _app_forward_topics(
                1, message("/appliance/uuid/publish"),
                response_topic="/app/1-abc123/subscribe"),
            ["/app/1/subscribe", "/app/1-abc123/subscribe"])

    def test_legacy_mode_can_be_disabled(self):
        self.assertEqual(
            _app_forward_topics(
                1, message("/appliance/uuid/publish"),
                legacy_user_topic_acks=False,
                response_topic="/app/1-abc123/subscribe"),
            ["/app/1-abc123/subscribe"])

    def test_device_response_header_from_is_not_used_as_a_topic(self):
        self.assertEqual(
            _app_forward_topics(
                1, message("/app/1-abc123/subscribe")),
            ["/app/1/subscribe"])

    def test_another_user_topic_is_never_used(self):
        self.assertEqual(
            _app_forward_topics(
                1, message("/appliance/uuid/publish"),
                response_topic="/app/2-abc123/subscribe"),
            ["/app/1/subscribe"])

    def test_missing_response_topic_falls_back_to_the_user_topic(self):
        self.assertEqual(
            _app_forward_topics(1, message("/appliance/uuid/publish")),
            ["/app/1/subscribe"])


class RememberAppResponseTest(unittest.TestCase):
    def test_records_the_requesting_app_topic(self):
        broker = broker_agent.Broker(
            hostname="localhost", port=2001, username="u", password="p",
            cert_ca=None, enable_bridging=False, device_timezone=None)
        db = SimpleNamespace(
            find_user_owner_by_device_uuid=lambda uuid: SimpleNamespace(
                user_id=1))
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._remember_app_response(
                "uuid", request("/app/1-abc123/subscribe", message_id="m1"))

        self.assertEqual(
            broker._app_response_topics["m1"], "/app/1-abc123/subscribe")

    def test_ignores_a_foreign_or_missing_topic(self):
        broker = broker_agent.Broker(
            hostname="localhost", port=2001, username="u", password="p",
            cert_ca=None, enable_bridging=False, device_timezone=None)
        db = SimpleNamespace(
            find_user_owner_by_device_uuid=lambda uuid: SimpleNamespace(
                user_id=1))
        with mock.patch.object(broker_agent, "dbhelper", db):
            broker._remember_app_response(
                "uuid", request("/app/2-abc123/subscribe", message_id="m1"))
            broker._remember_app_response(
                "uuid", request("/_agent", message_id="m2"))

        self.assertNotIn("m1", broker._app_response_topics)
        self.assertNotIn("m2", broker._app_response_topics)


if __name__ == "__main__":
    unittest.main()
