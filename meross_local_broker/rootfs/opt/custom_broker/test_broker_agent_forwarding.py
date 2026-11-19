# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Tests for the device-to-app delivery topics.

Run with: python3 -m unittest test_broker_agent_forwarding
"""

import unittest

from broker_agent import _app_forward_topics


def message(from_topic, method="GETACK"):
    return {"header": {"from": from_topic, "method": method}, "payload": {}}


class AppForwardTopicsTest(unittest.TestCase):
    def test_push_goes_to_the_user_topic_only(self):
        self.assertEqual(
            _app_forward_topics(
                1, message("/appliance/uuid/publish", method="PUSH")),
            ["/app/1/subscribe"])

    def test_command_ack_also_goes_to_the_app_topic(self):
        self.assertEqual(
            _app_forward_topics(1, message("/app/1-abc123/subscribe")),
            ["/app/1/subscribe", "/app/1-abc123/subscribe"])

    def test_legacy_mode_can_be_disabled(self):
        self.assertEqual(
            _app_forward_topics(
                1, message("/app/1-abc123/subscribe"),
                legacy_user_topic_acks=False),
            ["/app/1-abc123/subscribe"])

    def test_legacy_mode_falls_back_when_from_is_invalid(self):
        self.assertEqual(
            _app_forward_topics(
                1, message("/appliance/uuid/publish", method="PUSH"),
                legacy_user_topic_acks=False),
            ["/app/1/subscribe"])

    def test_same_topic_is_published_once(self):
        self.assertEqual(
            _app_forward_topics(1, message("/app/1/subscribe")),
            ["/app/1/subscribe"])

    def test_another_user_topic_is_never_used(self):
        self.assertEqual(
            _app_forward_topics(1, message("/app/2-abc123/subscribe")),
            ["/app/1/subscribe"])

    def test_invalid_or_missing_from_falls_back_to_the_user_topic(self):
        self.assertEqual(
            _app_forward_topics(1, message("http://evil/app/1/subscribe")),
            ["/app/1/subscribe"])
        self.assertEqual(
            _app_forward_topics(1, {"payload": {}}),
            ["/app/1/subscribe"])


if __name__ == "__main__":
    unittest.main()
