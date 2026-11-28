# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Tests for broker log redaction.

Run with: python3 -m unittest test_log_redaction
"""

import logging
import sys
import unittest

from log_redaction import RedactionFilter, Redactor

UUID = "24042648935315700804c7ae03aa3c11"
MAC = "AA:BB:CC:DD:EE:FF"
IP = "192.168.1.25"


class LogRedactionTest(unittest.TestCase):
    def test_redacts_identifiers_and_secrets(self):
        redactor = Redactor(b"secret")
        text = (
            f"device {UUID} mac {MAC} ip {IP} mail user@example.com "
            f'topic /app/1-abcdef123456/subscribe '
            f'payload {{"messageId":"{UUID}","sign":"0123456789abcdef"}}')

        first = redactor.redact(text)
        self.assertEqual(first, redactor.redact(text))
        for value in (UUID, MAC, IP, "user@example.com",
                      "abcdef123456", "0123456789abcdef"):
            self.assertNotIn(value, first)
        self.assertIn("uuid-", first)
        self.assertIn("app-", first)

    def test_loopback_is_kept(self):
        redactor = Redactor(b"secret")
        self.assertIn("127.0.0.1", redactor.redact("127.0.0.1:2002"))
        self.assertNotIn("10.0.0.5", redactor.redact("host 10.0.0.5"))

    def test_filter_redacts_exception_tracebacks(self):
        try:
            raise ValueError(f"device {UUID} at {IP}")
        except ValueError:
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            "broker_agent", logging.ERROR, __file__, 1,
            "request failed", (), exc_info)
        RedactionFilter(Redactor(b"secret")).filter(record)
        self.assertIn("Traceback", record.exc_text)
        self.assertNotIn(UUID, record.exc_text)
        self.assertNotIn(IP, record.exc_text)

    def test_filter_redacts_arguments(self):
        record = logging.LogRecord(
            "broker_agent", logging.INFO, __file__, 1,
            "device %s on %s", (UUID, IP), None)
        RedactionFilter(Redactor(b"secret")).filter(record)
        self.assertNotIn(UUID, record.msg)
        self.assertNotIn(IP, str(record.args))


if __name__ == "__main__":
    unittest.main()
