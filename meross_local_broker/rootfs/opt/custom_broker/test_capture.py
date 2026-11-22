# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Tests for the opt-in capture mode.

Run with: python3 -m unittest test_capture
"""

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from capture import CaptureManager


class Clock:
    def __init__(self):
        self.now = 1_763_546_400.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


UUID = "0123456789abcdef0123456789abcdef"


def payload(namespace, method, body, message_id="m1"):
    return {
        "header": {
            "messageId": message_id,
            "namespace": namespace,
            "method": method,
            "sign": "deadbeef",
            "from": f"/appliance/{UUID}/publish",
        },
        "payload": body,
    }


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.clock = Clock()
        self.manager = CaptureManager(
            str(Path(self.temporary.name) / "capture"), clock=self.clock)
        self.manager.start({"uuid": UUID, "type": "mrs100"})

    def frames(self):
        session = self.manager.session
        path = Path(session.directory) / "frames.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_frames_are_sanitized(self):
        self.manager.record(UUID, "rx", f"/appliance/{UUID}/publish",
                            payload("Appliance.RollerShutter.Position",
                                    "GETACK",
                                    {"channel": 0, "position": 42,
                                     "key": "secret",
                                     "mac": "AA:BB:CC:DD:EE:FF"}))

        frame = self.frames()[0]
        self.assertEqual(frame["namespace"],
                         "Appliance.RollerShutter.Position")
        self.assertEqual(frame["method"], "GETACK")
        self.assertEqual(frame["payload"]["position"], 42)
        self.assertNotIn("key", frame["payload"])
        self.assertNotIn("sign", frame)
        self.assertNotIn("messageId", frame)
        raw = json.dumps(frame)
        self.assertNotIn(UUID, raw)
        self.assertNotIn("AA:BB:CC:DD:EE:FF", raw)

    def test_session_metadata_is_redacted(self):
        session = self.manager.session
        metadata = json.loads(
            (Path(session.directory) / "session.json").read_text())
        self.assertNotEqual(metadata["device"]["uuid"], UUID)
        self.assertEqual(metadata["device"]["type"], "mrs100")

    def test_duration_limit_stops_the_capture(self):
        self.clock.advance(301)
        self.manager.record(UUID, "rx", "topic",
                            payload("Appliance.Test", "PUSH", {"value": 1}))

        status = self.manager.status()
        self.assertFalse(status["active"])
        self.assertEqual(status["reason"], "duration")
        self.assertEqual(self.frames(), [])

    def test_size_limit_stops_the_capture(self):
        self.manager.start(
            {"uuid": UUID, "type": "mrs100"}, max_bytes=1024)
        self.manager.record(UUID, "rx", "topic", payload(
            "Appliance.Test", "PUSH", {"blob": "x" * 2000}))

        status = self.manager.status()
        self.assertFalse(status["active"])
        self.assertEqual(status["reason"], "size")

    def test_restart_stops_the_previous_session(self):
        first = self.manager.status()["session_id"]
        self.manager.start({"uuid": UUID, "type": "mrs100"})
        second = self.manager.status()["session_id"]

        self.assertNotEqual(first, second)

    def test_draft_aggregates_namespaces_and_fields(self):
        self.manager.record(UUID, "rx", "topic", payload(
            "Appliance.RollerShutter.Position", "GETACK",
            {"channel": 0, "position": 42, "state": 1}))
        self.manager.record(UUID, "rx", "topic", payload(
            "Appliance.RollerShutter.Position", "PUSH",
            {"channel": 0, "position": 20, "state": 2}))
        self.manager.record(UUID, "tx", "topic", payload(
            "Appliance.RollerShutter.State", "SET",
            {"channel": 0, "state": 1}))

        result = self.manager.build_draft("mrs100")

        self.assertEqual(result["namespaces"], 2)
        draft_path = Path(result["path"])
        text = draft_path.read_text()
        self.assertIn("draft.mrs100", text)
        self.assertIn("Appliance.RollerShutter.Position", text)
        self.assertIn("methods:", text)
        self.assertIn("position:", text)

    def test_draft_rejects_an_invalid_type(self):
        with self.assertRaises(ValueError):
            self.manager.build_draft("Not A Type!")

    def test_a_second_process_records_into_the_active_session(self):
        # The broker agent creates its manager at startup, before the API
        # process starts a capture.
        recorder = CaptureManager(self.manager.directory, clock=self.clock)
        recorder.record(UUID, "rx", f"/appliance/{UUID}/publish",
                        payload("Appliance.RollerShutter.State", "PUSH",
                                {"channel": 0, "state": 2}))

        status = self.manager.status()
        self.assertTrue(status["active"])
        self.assertEqual(status["frames"], 1)
        self.assertGreater(status["bytes"], 0)
        self.assertEqual(len(self.frames()), 1)

    def test_stop_from_the_controller_stops_the_recorder(self):
        recorder = CaptureManager(self.manager.directory, clock=self.clock)
        recorder.record(UUID, "rx", "topic",
                        payload("Appliance.Test", "PUSH", {"value": 1}))
        self.manager.stop()

        recorder.record(UUID, "rx", "topic",
                        payload("Appliance.Test", "PUSH", {"value": 2}))

        status = recorder.status()
        self.assertFalse(status["active"])
        self.assertEqual(status["reason"], "user")
        self.assertEqual(status["frames"], 1)

    def test_frames_from_other_devices_are_ignored(self):
        self.manager.record("f" * 32, "rx", "topic",
                            payload("Appliance.Test", "PUSH", {"value": 1}))

        self.assertEqual(self.manager.status()["frames"], 0)

    def test_export_zip_contains_session_frames_and_draft(self):
        self.manager.record(UUID, "rx", "topic", payload(
            "Appliance.RollerShutter.Position", "PUSH",
            {"channel": 0, "position": 20}))
        name, content = self.manager.export_zip()

        self.assertTrue(name.startswith("capture-"))
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"session.json", "frames.jsonl", "draft.yaml"})
            frames = archive.read("frames.jsonl").decode("utf-8")
            self.assertIn("Appliance.RollerShutter.Position", frames)
            self.assertNotIn(UUID, frames)
            self.assertIn("draft.mrs100",
                          archive.read("draft.yaml").decode("utf-8"))

    def test_export_zip_drops_a_partial_last_frame(self):
        self.manager.record(UUID, "rx", "topic",
                            payload("Appliance.Test", "PUSH", {"value": 1}))
        with open(self.manager.session.frames_path, "ab") as handle:
            handle.write(b'{"ts":0,"dir":"rx"')

        _, content = self.manager.export_zip()

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            frames = archive.read("frames.jsonl").decode("utf-8")
        self.assertEqual(len(frames.splitlines()), 1)

    def test_restart_from_the_controller_rebinds_the_recorder(self):
        recorder = CaptureManager(self.manager.directory, clock=self.clock)
        recorder.record(UUID, "rx", "topic",
                        payload("Appliance.Test", "PUSH", {"value": 1}))
        self.manager.start({"uuid": UUID, "type": "mrs100"})
        recorder.record(UUID, "rx", "topic",
                        payload("Appliance.Test", "PUSH", {"value": 2}))

        status = self.manager.status()
        self.assertTrue(status["active"])
        self.assertEqual(status["frames"], 1)
        self.assertEqual(recorder.status()["session_id"],
                         status["session_id"])


if __name__ == "__main__":
    unittest.main()
