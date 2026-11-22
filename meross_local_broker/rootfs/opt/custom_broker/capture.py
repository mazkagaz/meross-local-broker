# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0)
"""Opt-in MQTT frame capture and profile draft generation.

Sessions are written under /data/capture with restricted permissions. Frames
are sanitized before being persisted: secrets are dropped, identifiers are
pseudonymized with the installation key and message ids are never stored.
A draft aggregates the observed namespaces, methods and payload shapes; it is
a starting point for a human author, not an active profile.

The control endpoints run in the API process while frames are observed by the
broker agent process. A small ``current.json`` control file names the active
session; the agent follows it and appends frames, and the API derives status
from the same files. Only frames of the captured device are kept.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
import time
import zipfile
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
_CURRENT_FILE = "current.json"


def _control_path(directory: str) -> str:
    return os.path.join(directory, _CURRENT_FILE)


def _read_control(directory: str) -> Optional[Dict[str, Any]]:
    try:
        with open(_control_path(directory), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_control(directory: str, session: "CaptureSession",
                   force: bool = False) -> None:
    """Publish the active session for the other process.

    A late stop from the recorder must not overwrite a session that the API
    has already replaced, unless it targets the same session.
    """
    existing = _read_control(directory)
    if not force and existing is not None and \
            existing.get("session_id") != session.session_id:
        return
    path = _control_path(directory)
    temporary = path + ".tmp"
    data = {
        "session_id": session.session_id,
        "stopped_at": session.stopped_at,
        "reason": session.reason,
    }
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


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


def _device_tag(device_uuid: str) -> str:
    """Stable, non-reversible tag shared by the API and broker processes."""
    value = str(device_uuid or "").strip().lower().encode("utf8")
    return hashlib.sha256(value).hexdigest()[:16] if value else ""


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
    """One on-disk capture session shared by the API and broker processes."""

    def __init__(self, directory: str, device: Dict[str, Any],
                 duration_s: int, max_bytes: int, session_id: str,
                 clock=time.time) -> None:
        self.directory = directory
        self.clock = clock
        self.session_id = session_id
        self.started_at = clock()
        self.deadline = self.started_at + duration_s
        self.max_bytes = max_bytes
        self.stopped_at: Optional[float] = None
        self.reason: Optional[str] = None
        device_uuid = str(device.get("uuid") or "")
        self.device_tag = _device_tag(device_uuid)
        device = _sanitize(dict(device))
        device["uuid"] = redact_text(device_uuid)
        self.metadata = {
            "schema_version": 1,
            "session_id": self.session_id,
            "device": device,
            "device_tag": self.device_tag,
            "started_at": self.started_at,
            "deadline": self.deadline,
            "max_bytes": self.max_bytes,
            "stopped_at": None,
            "reason": None,
        }
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        os.chmod(self.directory, 0o700)
        self.metadata_path = os.path.join(directory, "session.json")
        self.frames_path = os.path.join(directory, "frames.jsonl")
        self._frames = self._count_frames()
        self._write_metadata()

    @classmethod
    def load(cls, directory: str, clock=time.time) -> "CaptureSession":
        path = os.path.join(directory, "session.json")
        with open(path, "r", encoding="utf-8") as handle:
            metadata = json.load(handle)
        if not isinstance(metadata, dict):
            raise ValueError("Invalid capture session")
        session = cls.__new__(cls)
        session.directory = directory
        session.clock = clock
        session.session_id = str(
            metadata.get("session_id") or os.path.basename(directory))
        session.started_at = float(metadata.get("started_at") or 0)
        deadline = metadata.get("deadline")
        session.deadline = (
            float(deadline) if deadline is not None
            else session.started_at + DEFAULT_DURATION_S)
        session.max_bytes = int(metadata.get("max_bytes") or DEFAULT_MAX_BYTES)
        stopped_at = metadata.get("stopped_at")
        session.stopped_at = (
            float(stopped_at) if stopped_at is not None else None)
        session.reason = metadata.get("reason")
        session.metadata = metadata
        session.device_tag = str(metadata.get("device_tag") or "")
        session.metadata_path = path
        session.frames_path = os.path.join(directory, "frames.jsonl")
        session._frames = session._count_frames()
        return session

    def _count_frames(self) -> int:
        try:
            with open(self.frames_path, "r", encoding="utf-8") as handle:
                return sum(1 for _ in handle)
        except OSError:
            return 0

    def _size(self) -> int:
        try:
            return os.path.getsize(self.frames_path)
        except OSError:
            return 0

    def _write_metadata(self) -> None:
        temporary = self.metadata_path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self.metadata, handle, indent=1)
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.metadata_path)

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
        if self._size() + len(line) > self.max_bytes or \
                self._frames >= MAX_FRAMES:
            self.stop("size")
            return
        with open(self.frames_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        os.chmod(self.frames_path, 0o600)
        self._frames += 1

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
        _write_control(os.path.dirname(self.directory), self)
        _LOG.info("Capture %s stopped (%s, %d frames)",
                  self.session_id, reason, self._count_frames())

    def status(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "active": self.active(),
            "frames": self._count_frames(),
            "bytes": self._size(),
            "reason": self.reason,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
        }


class CaptureManager:
    """At most one active capture session at a time.

    Every process derives the session from disk, so starting a capture from
    the API process is visible to the broker agent that records the frames.
    """

    def __init__(self, directory: str = CAPTURE_DIR,
                 clock=time.time) -> None:
        self.directory = directory
        self.clock = clock
        self.session: Optional[CaptureSession] = None

    def _refresh(self) -> Optional[CaptureSession]:
        control = _read_control(self.directory)
        if control is None:
            self.session = None
            return None
        session_id = control.get("session_id")
        if not isinstance(session_id, str) or not session_id or \
                session_id != os.path.basename(session_id):
            self.session = None
            return None
        session = self.session
        if session is None or session.session_id != session_id:
            path = os.path.join(self.directory, session_id)
            try:
                session = CaptureSession.load(path, clock=self.clock)
            except (OSError, ValueError, TypeError, KeyError):
                self.session = None
                return None
            self.session = session
        stopped_at = control.get("stopped_at")
        if stopped_at is not None and session.active():
            session.stopped_at = float(stopped_at)
            session.reason = control.get("reason")
        return session

    def start(self, device: Dict[str, Any], duration_s: int = DEFAULT_DURATION_S,
              max_bytes: int = DEFAULT_MAX_BYTES) -> Dict[str, Any]:
        if str(device.get("uuid") or "") == "":
            raise ValueError("Missing device uuid")
        current = self._refresh()
        if current is not None and current.active():
            current.stop("restarted")
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
        _write_control(self.directory, self.session, force=True)
        _LOG.info("Capture %s started for %s", self.session.session_id,
                  device.get("type"))
        return self.session.status()

    def stop(self) -> Optional[Dict[str, Any]]:
        session = self._refresh()
        if session is None:
            return None
        session.stop("user")
        return session.status()

    def status(self) -> Optional[Dict[str, Any]]:
        session = self._refresh()
        return session.status() if session is not None else None

    def record(self, device_uuid: str, direction: str, topic: str,
               payload: Dict[str, Any]) -> None:
        try:
            session = self._refresh()
            if session is None or not session.active():
                return
            if session.device_tag and \
                    _device_tag(str(device_uuid)) != session.device_tag:
                return
            session.record(direction, topic, payload)
        except Exception as ex:  # noqa: BLE001 - capture is best effort
            _LOG.debug("Capture record failed: %s", ex)

    def _read_frames(self, session: CaptureSession) -> Optional[bytes]:
        try:
            with open(session.frames_path, "rb") as handle:
                data = handle.read()
        except OSError:
            return None
        if data and not data.endswith(b"\n"):
            # A recorder may be in the middle of an append: drop the partial
            # last line so the archive stays valid JSONL.
            cut = data.rfind(b"\n")
            data = data[:cut + 1] if cut >= 0 else b""
        return data

    def export_zip(self) -> tuple[str, bytes]:
        """Bundle the session metadata, frames and draft for download."""
        session = self._refresh()
        if session is None:
            raise ValueError("No capture session")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr(
                "session.json", json.dumps(session.metadata, indent=1))
            bundle.writestr("frames.jsonl", self._read_frames(session) or b"")
            draft_path = os.path.join(session.directory, "draft.yaml")
            if not os.path.exists(draft_path):
                device = session.metadata.get("device")
                device_type = (device or {}).get("type") \
                    if isinstance(device, dict) else None
                if isinstance(device_type, str) and \
                        _PROFILE_ID_RE.fullmatch(device_type):
                    try:
                        self.build_draft(device_type)
                    except (OSError, ValueError):
                        pass
            if os.path.exists(draft_path):
                with open(draft_path, "r", encoding="utf-8") as handle:
                    bundle.writestr("draft.yaml", handle.read())
        return f"capture-{session.session_id}.zip", buffer.getvalue()

    def build_draft(self, device_type: str) -> Dict[str, Any]:
        session = self._refresh()
        if session is None:
            raise ValueError("No capture session")
        if not _PROFILE_ID_RE.fullmatch(device_type or ""):
            raise ValueError("Invalid device type")
        namespaces: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(session.frames_path):
            with open(session.frames_path, "r", encoding="utf-8") as handle:
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
            "frames": session._count_frames(),
        }


_manager: Optional[CaptureManager] = None

def get_capture_manager() -> CaptureManager:
    global _manager
    if _manager is None:
        _manager = CaptureManager()
    return _manager
