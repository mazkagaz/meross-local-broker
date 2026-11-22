# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0)
"""Opt-in MQTT frame capture and profile draft generation.

Sessions are written under /data/capture with restricted permissions. Frames
are sanitized before being persisted: secrets are dropped, identifiers are
pseudonymized with the installation key and message ids are never stored.
A draft aggregates the observed namespaces, methods and payload shapes; it is
a starting point for a human author, not an active profile.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time
from typing import Any, Dict, Optional

import yaml

from logger import get_logger
from log_redaction import redact_text

_LOG = get_logger(__name__)

CAPTURE_DIR = "/data/capture"
DEFAULT_DURATION_S = 300
DEFAULT_MAX_BYTES = 2_000_000
MAX_FRAMES = 2000
_SECRET_KEYS = {
    "sign", "messageid", "key", "token", "mqttkey", "password",
    "wifipassword", "ssid", "bindid",
}
_PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in _SECRET_KEYS:
                continue
            result[key] = _sanitize(item)
        return result
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def sanitize(value: Any) -> Any:
    """Public wrapper for callers that return device data to the admin UI."""
    return _sanitize(value)


def _infer_field(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return {
            "type": "object",
            "fields": {key: _infer_field(item) for key, item in value.items()},
        }
    if isinstance(value, list):
        item = value[0] if value else None
        return {"type": "array", "items": _infer_field(item)}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    return {"type": "string"}


class CaptureSession:
    def __init__(self, directory: str, device: Dict[str, Any],
                 duration_s: int, max_bytes: int, session_id: str,
                 clock=time.time) -> None:
        self.directory = directory
        self.clock = clock
        self.started_at = clock()
        self.deadline = self.started_at + duration_s
        self.max_bytes = max_bytes
        self.size = 0
        self.frames = 0
        self.stopped_at: Optional[float] = None
        self.reason: Optional[str] = None
        self.session_id = session_id
        device = _sanitize(dict(device))
        device["uuid"] = redact_text(str(device.get("uuid") or ""))
        self.metadata = {
            "schema_version": 1,
            "session_id": self.session_id,
            "device": device,
            "started_at": self.started_at,
            "stopped_at": None,
            "reason": None,
        }
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        os.chmod(self.directory, 0o700)
        self._frames_path = os.path.join(directory, "frames.jsonl")
        self._write_metadata()

    def _write_metadata(self) -> None:
        path = os.path.join(self.directory, "session.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.metadata, handle, indent=1)
        os.chmod(path, 0o600)

    def active(self) -> bool:
        return self.stopped_at is None

    def record(self, direction: str, topic: str, payload: Dict[str, Any],
               ) -> None:
        if not self.active():
            return
        now = self.clock()
        if now >= self.deadline:
            self.stop("duration")
            return
        header = payload.get("header") if isinstance(payload, dict) else None
        header = header if isinstance(header, dict) else {}
        frame = {
            "ts": round(now - self.started_at, 3),
            "dir": direction,
            "topic": redact_text(topic),
            "namespace": header.get("namespace"),
            "method": header.get("method"),
            "payload": _sanitize(payload.get("payload")
                                 if isinstance(payload, dict) else None),
        }
        line = json.dumps(frame, separators=(",", ":"))
        if self.size + len(line) > self.max_bytes or self.frames >= MAX_FRAMES:
            self.stop("size")
            return
        with open(self._frames_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        os.chmod(self._frames_path, 0o600)
        self.size += len(line)
        self.frames += 1

    def stop(self, reason: str) -> None:
        if not self.active():
            return
        self.stopped_at = self.clock()
        self.reason = reason
        self.metadata.update({
            "stopped_at": self.stopped_at,
            "reason": reason,
        })
        self._write_metadata()
        _LOG.info("Capture %s stopped (%s, %d frames)",
                  self.session_id, reason, self.frames)

    def status(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "active": self.active(),
            "frames": self.frames,
            "bytes": self.size,
            "reason": self.reason,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
        }


class CaptureManager:
    """At most one active capture session at a time."""

    def __init__(self, directory: str = CAPTURE_DIR,
                 clock=time.time) -> None:
        self.directory = directory
        self.clock = clock
        self.session: Optional[CaptureSession] = None

    def start(self, device: Dict[str, Any], duration_s: int = DEFAULT_DURATION_S,
              max_bytes: int = DEFAULT_MAX_BYTES) -> Dict[str, Any]:
        if str(device.get("uuid") or "") == "":
            raise ValueError("Missing device uuid")
        if self.session is not None and self.session.active():
            self.session.stop("restarted")
        session_id = time.strftime(
            "%Y%m%dT%H%M%SZ", time.gmtime(self.clock())) + \
            f"-{secrets.token_hex(3)}"
        directory = os.path.join(self.directory, session_id)
        self.session = CaptureSession(
            directory, device,
            max(1, min(int(duration_s), 3600)),
            max(1024, min(int(max_bytes), 20_000_000)),
            session_id=session_id,
            clock=self.clock)
        _LOG.info("Capture %s started for %s", self.session.session_id,
                  device.get("type"))
        return self.session.status()

    def stop(self) -> Optional[Dict[str, Any]]:
        if self.session is None:
            return None
        self.session.stop("user")
        return self.session.status()

    def status(self) -> Optional[Dict[str, Any]]:
        return self.session.status() if self.session is not None else None

    def record(self, device_uuid: str, direction: str, topic: str,
               payload: Dict[str, Any]) -> None:
        try:
            session = self.session
            if session is None or not session.active():
                return
            session.record(direction, topic, payload)
        except Exception as ex:  # noqa: BLE001 - capture is best effort
            _LOG.debug("Capture record failed: %s", ex)

    def build_draft(self, device_type: str) -> Dict[str, Any]:
        session = self.session
        if session is None:
            raise ValueError("No capture session")
        if not _PROFILE_ID_RE.fullmatch(device_type or ""):
            raise ValueError("Invalid device type")
        namespaces: Dict[str, Dict[str, Any]] = {}
        frames_path = os.path.join(session.directory, "frames.jsonl")
        if os.path.exists(frames_path):
            with open(frames_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        frame = json.loads(line)
                    except ValueError:
                        continue
                    namespace = frame.get("namespace")
                    if not isinstance(namespace, str):
                        continue
                    entry = namespaces.setdefault(namespace, {
                        "methods": set(), "fields": {}})
                    method = frame.get("method")
                    if isinstance(method, str):
                        entry["methods"].add(method)
                    payload = frame.get("payload")
                    if isinstance(payload, dict):
                        for key, value in payload.items():
                            entry["fields"].setdefault(
                                key, _infer_field(value))
        draft = {
            "schema_version": 2,
            "profile": {
                "id": f"draft.{device_type}",
                "version": "0.1.0",
                "requires_engine": ">=2.2",
                "description": "Brouillon généré depuis une capture.",
            },
            "match": {"type": [device_type]},
            "payloads": {
                namespace: {
                    "methods": sorted(entry["methods"]),
                    "fields": entry["fields"],
                }
                for namespace, entry in sorted(namespaces.items())
                if entry["methods"]
            },
            "entities": [],
        }
        path = os.path.join(session.directory, "draft.yaml")
        header = (
            "# Brouillon généré depuis une capture. Compléter les entités\n"
            "# puis déplacer le fichier dans /data/device_profiles.\n")
        text = header + yaml.safe_dump(
            draft, sort_keys=False, allow_unicode=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(path, 0o600)
        return {
            "path": path,
            "yaml": text,
            "namespaces": len(draft["payloads"]),
            "frames": session.frames,
        }


_manager: Optional[CaptureManager] = None


def get_capture_manager() -> CaptureManager:
    global _manager
    if _manager is None:
        _manager = CaptureManager()
    return _manager
