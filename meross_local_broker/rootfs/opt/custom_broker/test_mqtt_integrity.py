"""Tests for device MQTT signature, freshness and replay checks."""
from hashlib import md5
import unittest

import mqtt_integrity

DEVICE_UUID = "deviceuuid"
DEVICE_KEY = "device-key"


def build_message(timestamp, message_id="message-id", key=DEVICE_KEY, signature=None):
    if signature is None:
        signature = md5(f"{message_id}{key}{timestamp}".encode("utf8")).hexdigest()
    return {
        "header": {
            "messageId": message_id,
            "timestamp": timestamp,
            "sign": signature,
        }
    }


class DeviceMessageIntegrityTest(unittest.TestCase):
    def setUp(self):
        mqtt_integrity.reset_cache()

    def test_valid_signature_and_fresh_timestamp(self):
        payload = build_message(1_700_000_000)
        ok, reason = mqtt_integrity.evaluate(
            DEVICE_UUID, payload, DEVICE_KEY, now=1_700_000_000)
        self.assertTrue(ok, reason)

    def test_invalid_signature(self):
        payload = build_message(1_700_000_000, signature="0" * 32)
        ok, reason = mqtt_integrity.evaluate(
            DEVICE_UUID, payload, DEVICE_KEY, now=1_700_000_000)
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_signature")

    def test_stale_timestamp(self):
        payload = build_message(1_700_000_000)
        ok, reason = mqtt_integrity.evaluate(
            DEVICE_UUID, payload, DEVICE_KEY,
            now=1_700_000_000 + mqtt_integrity.MAX_SKEW_SECONDS + 1)
        self.assertFalse(ok)
        self.assertEqual(reason, "stale_timestamp")

    def test_replay_is_rejected_after_first_use(self):
        payload = build_message(1_700_000_000)
        self.assertTrue(mqtt_integrity.evaluate(
            DEVICE_UUID, payload, DEVICE_KEY, now=1_700_000_000)[0])
        ok, reason = mqtt_integrity.evaluate(
            DEVICE_UUID, payload, DEVICE_KEY, now=1_700_000_000)
        self.assertFalse(ok)
        self.assertEqual(reason, "replay")

    def test_millisecond_timestamp_is_accepted(self):
        timestamp_ms = 1_700_000_000_000
        payload = build_message(timestamp_ms)
        ok, reason = mqtt_integrity.evaluate(
            DEVICE_UUID, payload, DEVICE_KEY, now=1_700_000_000)
        self.assertTrue(ok, reason)

    def test_missing_signature_fields(self):
        ok, reason = mqtt_integrity.evaluate(
            DEVICE_UUID, {"header": {}}, DEVICE_KEY, now=1_700_000_000)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_signature_fields")

    def test_warning_is_rate_limited(self):
        self.assertTrue(mqtt_integrity.should_log(DEVICE_UUID, "invalid_signature"))
        self.assertFalse(mqtt_integrity.should_log(DEVICE_UUID, "invalid_signature"))


if __name__ == "__main__":
    unittest.main()
