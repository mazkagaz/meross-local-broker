# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Backend for the device/profile tuning page (V1).

All writes target /data/device_profiles overrides only. The bundled catalog is
read-only. Parsing is data-only (safe_load); no profile is executed.
"""
from __future__ import annotations

import difflib
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import ssl
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import paho.mqtt.client as mqtt
import yaml

import profile_engine
import profile_match
from capture import sanitize
from compat import OnlineStatus
from db_helper import dbhelper
from profile_lint import DEFAULT_SCHEMA, lint_documents, load_schema
from profiles import ProfileCatalog, get_catalog, reload_catalog
from protocol import _build_mqtt_message

MAX_YAML_BYTES = 256 * 1024
MAX_YAML_LINES = 5000
MAX_DEPTH = 32
MAX_BACKUPS_PER_PROFILE = 20
MAX_EXPORT_PROFILES = 200
PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
DEFAULT_OVERRIDES = Path("/data/device_profiles")
DEFAULT_BACKUPS = Path("/data/profile_backups")
DEFAULT_AUDIT = Path("/data/profile_audit.jsonl")
STATE_METHODS = ("GETACK", "SETACK", "PUSH")
READ_TIMEOUT_DEFAULT = 6.0
READ_TIMEOUT_MAX = 15.0
READ_COOLDOWN_DEFAULT = 2.0
COMMAND_COOLDOWN_DEFAULT = 1.0
COMMAND_TOKEN_TTL = 60.0
MAX_SIMULATION_CHANNEL = 64
SYSTEM_ALL = "Appliance.System.All"
SYSTEM_ABILITY = "Appliance.System.Ability"


class TuningError(ValueError):
    """Invalid request or profile content."""


class TuningNotFound(TuningError):
    """Unknown profile, device or backup."""


class TuningConflict(TuningError):
    """Optimistic-lock conflict or unavailable target."""


class TuningRateLimited(TuningError):
    """Too many live reads for one device."""

    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = max(1, int(round(retry_after)))


class TuningTimeout(TuningError):
    """The device did not answer in time."""


class TuningUnavailable(TuningError):
    """The local MQTT broker could not be reached."""


@dataclass
class ValidationResult:
    valid: bool
    profile_id: Optional[str]
    errors: List[str]
    warnings: List[str]
    summary: Dict[str, Any]
    data: Optional[Dict[str, Any]] = None
    diff: str = ""
    diff_base: Optional[str] = None

    def serialize(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "profile_id": self.profile_id,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": self.summary,
            "diff": self.diff,
            "diff_base": self.diff_base,
        }


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_text(text: str) -> str:
    return _hash_bytes(text.encode("utf-8"))


def _depth(value: Any, current: int = 1) -> int:
    if isinstance(value, dict):
        return max([current] + [
            _depth(item, current + 1) for item in value.values()])
    if isinstance(value, list):
        return max([current] + [
            _depth(item, current + 1) for item in value])
    return current


def _yaml_text(data: Dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


class MqttProbe:
    """One read-only GET round-trip against the local broker.

    The probe connects as an app user derived from the device owner, sends a
    signed GET and waits for the matching GETACK. It never sends SET and never
    subscribes to another user's topics.
    """

    def __init__(self, host: str = "localhost", port: int = 2001,
                 ca: str = "/data/mqtt/certs/ca.crt",
                 connect_timeout: float = 5.0) -> None:
        self.host = host
        self.port = int(port)
        self.ca = ca
        self.connect_timeout = connect_timeout

    def read(self, device_uuid: str, user: Any, namespace: str,
             payload: Optional[Dict[str, Any]] = None,
             timeout: float = READ_TIMEOUT_DEFAULT) -> Dict[str, Any]:
        return self.send(device_uuid, user, "GET", namespace,
                         payload, timeout)

    def send(self, device_uuid: str, user: Any, method: str,
             namespace: str, payload: Optional[Dict[str, Any]] = None,
             timeout: float = READ_TIMEOUT_DEFAULT) -> Dict[str, Any]:
        user_id = str(user.user_id)
        suffix = secrets.token_hex(4)
        response_topic = f"/app/{user_id}-tuning{suffix}/subscribe"
        message, message_id = _build_mqtt_message(
            method=method, namespace=namespace, payload=payload or {},
            dev_key=user.mqtt_key, header_from=response_topic)
        password = md5(f"{user_id}{user.mqtt_key}".encode()).hexdigest()

        client = mqtt.Client(
            client_id=f"app:{user_id}_tuning{suffix}",
            clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        client.username_pw_set(username=user_id, password=password)
        context = ssl.create_default_context(cafile=self.ca)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        client.tls_set_context(context)

        received: Dict[str, Any] = {}
        connected = threading.Event()
        answered = threading.Event()

        def on_connect(_client, _userdata, _flags, rc):
            if rc == 0:
                connected.set()

        def on_message(_client, _userdata, message):
            try:
                data = json.loads(message.payload)
            except (TypeError, ValueError):
                return
            header = (data.get("header")
                      if isinstance(data, dict) else None)
            if not isinstance(header, dict):
                return
            if header.get("messageId") != message_id:
                return
            if header.get("namespace") != namespace:
                return
            origin = header.get("from")
            if origin not in (None, f"/appliance/{device_uuid}/publish"):
                return
            received["data"] = data
            answered.set()

        client.on_connect = on_connect
        client.on_message = on_message
        started = time.monotonic()
        try:
            client.connect(self.host, self.port, keepalive=60)
        except (OSError, ssl.SSLError) as error:
            raise TuningUnavailable(
                "cannot reach the local MQTT broker") from error
        client.loop_start()
        try:
            if not connected.wait(self.connect_timeout):
                raise TuningUnavailable(
                    "the local MQTT broker did not accept the connection")
            client.subscribe(response_topic, qos=1)
            client.publish(f"/appliance/{device_uuid}/subscribe",
                           message, qos=1)
            if not answered.wait(timeout):
                raise TuningTimeout(
                    f"device did not answer within {timeout:g}s")
        finally:
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001 - teardown is best effort
                pass
            client.loop_stop()
        elapsed_ms = round((time.monotonic() - started) * 1000)
        data = received["data"]
        header = data.get("header") or {}
        method = header.get("method")
        safe_header = {
            key: value for key, value in header.items()
            if key not in ("sign", "messageId")
        }
        return {
            "uuid": device_uuid,
            "namespace": namespace,
            "method": method,
            "ok": method != "ERROR",
            "header": sanitize(safe_header),
            "payload": sanitize(data.get("payload") or {}),
            "elapsed_ms": elapsed_ms,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }


class TuningStore:
    """Profile overrides, validation, import/export and audit."""

    def __init__(self, overrides: Path = DEFAULT_OVERRIDES,
                 backups: Path = DEFAULT_BACKUPS,
                 audit: Path = DEFAULT_AUDIT,
                 schema: Path = DEFAULT_SCHEMA,
                 catalog_getter=get_catalog,
                 catalog_reloader=reload_catalog,
                 devices=dbhelper.get_all_devices,
                 ability=dbhelper.get_device_ability,
                 statuses=dbhelper.get_roller_shutter_statuses,
                 configs=dbhelper.get_roller_shutter_configs,
                 adjusts=dbhelper.get_roller_shutter_adjusts,
                 set_ability=dbhelper.set_device_ability,
                 probe: Optional[MqttProbe] = None,
                 clock=time.monotonic,
                 read_cooldown: float = READ_COOLDOWN_DEFAULT,
                 read_timeout: float = READ_TIMEOUT_DEFAULT,
                 command_cooldown: float = COMMAND_COOLDOWN_DEFAULT,
                 command_token_ttl: float = COMMAND_TOKEN_TTL) -> None:
        self.overrides = Path(overrides)
        self.backups = Path(backups)
        self.audit = Path(audit)
        self.schema = Path(schema)
        self._catalog_getter = catalog_getter
        self._catalog_reloader = catalog_reloader
        self._devices = devices
        self._ability = ability
        self._statuses = statuses
        self._configs = configs
        self._adjusts = adjusts
        self._set_ability = set_ability
        self._last_ability: Dict[str, float] = {}
        self._ability_lock = threading.Lock()
        self._probe = probe
        self._clock = clock
        self._read_cooldown = float(read_cooldown)
        self._read_timeout = float(read_timeout)
        self._last_read: Dict[str, float] = {}
        self._read_lock = threading.Lock()
        self._command_cooldown = float(command_cooldown)
        self._command_token_ttl = float(command_token_ttl)
        self._command_tokens: Dict[str, Dict[str, Any]] = {}
        self._last_command: Dict[str, float] = {}
        self._busy_devices: set = set()
        self._command_lock = threading.Lock()
        self._validator = load_schema(self.schema)

    # -- inventory -----------------------------------------------------
    def catalog(self) -> ProfileCatalog:
        return self._catalog_getter()

    def list_profiles(self) -> List[Dict[str, Any]]:
        catalog = self.catalog()
        matches = self._match_devices(catalog)
        impact: Dict[str, int] = {}
        for profile_id in matches.values():
            if profile_id:
                impact[profile_id] = impact.get(profile_id, 0) + 1
        result = []
        for profile_id in sorted(catalog.profiles):
            data = catalog.profiles[profile_id]
            override = self._override_path(profile_id)
            result.append({
                "id": profile_id,
                "version": data["profile"].get("version"),
                "source": catalog.sources.get(profile_id, "bundled"),
                "hash": catalog.profile_hashes()[profile_id],
                "requires_engine": data["profile"].get("requires_engine"),
                "devices_affected": impact.get(profile_id, 0),
                "override_file": override.name if override else None,
            })
        return result

    def list_devices(self) -> List[Dict[str, Any]]:
        catalog = self.catalog()
        matches = self._match_devices(catalog)
        devices = []
        for device in self._devices():
            devices.append({
                "uuid": device.uuid,
                "name": device.dev_name,
                "type": device.device_type,
                "sub_type": device.sub_type,
                "online": (device.online_status.value
                           if device.online_status is not None else None),
                "profile": matches.get(device.uuid),
                "channels": [channel.channel_id for channel in
                             device.channels],
                "subdevices": [
                    {"id": sub.sub_device_id,
                     "type": sub.sub_device_type,
                     "name": sub.sub_device_name}
                    for sub in device.child_subdevices
                ],
            })
        return devices

    @staticmethod
    def _profile_meta(catalog: ProfileCatalog,
                      profile_id: str) -> profile_engine.ProfileMeta:
        return profile_match.profile_meta(catalog, profile_id)

    def _match_devices(self, catalog: ProfileCatalog) -> Dict[str, str]:
        matches = profile_match.match_devices(
            catalog, self._devices(), self._ability)
        return {
            uuid: (info["id"] if info else "")
            for uuid, info in matches.items()
        }

    def get_profile(self, profile_id: str) -> Dict[str, Any]:
        catalog = self.catalog()
        data = catalog.profiles.get(profile_id)
        if data is None:
            raise TuningNotFound(f"unknown profile {profile_id}")
        override = self._override_path(profile_id)
        bundled = self._bundled_path(profile_id)
        override_text = override.read_text() if override else None
        bundled_text = bundled.read_text() if bundled else _yaml_text(data)
        diff = ""
        if override_text is not None:
            diff = self._diff(
                bundled_text, override_text,
                f"{profile_id}.yaml (bundled)",
                f"{profile_id}.yaml (override)")
        return {
            "id": profile_id,
            "version": data["profile"].get("version"),
            "source": catalog.sources.get(profile_id, "bundled"),
            "catalog_hash": catalog.profile_hashes()[profile_id],
            "override_hash": (_hash_text(override_text)
                              if override_text is not None else None),
            "revision": catalog.revision,
            "yaml": _yaml_text(data),
            "override_yaml": override_text,
            "bundled_yaml": bundled_text,
            "diff": diff,
            "devices_affected": next(
                (item["devices_affected"] for item in self.list_profiles()
                 if item["id"] == profile_id), 0),
            "backups": self.list_backups(profile_id),
        }

    # -- device inspection and simulation -----------------------------
    def _device(self, uuid: str) -> Any:
        for device in self._devices():
            if device.uuid == uuid:
                return device
        return None

    @staticmethod
    def _iso(value: Any) -> Any:
        return value.isoformat() if hasattr(value, "isoformat") else value

    @staticmethod
    def _entity_rows(entities) -> List[Dict[str, Any]]:
        rows = []
        for entity in entities.values():
            state = entity.state
            rows.append({
                "key": entity.key,
                "platform": entity.platform,
                "name": entity.name,
                "channel": entity.channel,
                "device": entity.device,
                "namespace": (state.namespace
                              if state is not None else None),
                "fields": sorted(state.fields) if state is not None else [],
                "commands": sorted(entity.commands),
            })
        return sorted(rows, key=lambda row: (row["platform"], row["key"]))

    @staticmethod
    def _json_or_none(text: Optional[str]) -> Any:
        if not text:
            return None
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_rows(getter, uuid: str, errors: List[str],
                   row) -> List[Dict[str, Any]]:
        try:
            return [row(item) for item in getter(uuid)]
        except Exception as error:  # noqa: BLE001 - diagnostics stay isolated
            errors.append(f"cache read failed: {type(error).__name__}")
            return []

    @staticmethod
    def _polling_rows(namespaces, scope: str) -> List[Dict[str, Any]]:
        rows = []
        for name, spec in sorted(namespaces.items()):
            rows.append({
                "namespace": name,
                "scope": scope,
                "methods": list(spec.methods),
                "strategy": spec.polling.strategy,
                "period_s": spec.polling.period_s,
                "push": spec.polling.push,
                "response_size": spec.polling.response_size,
            })
        return rows

    def device_state(self, uuid: str) -> Dict[str, Any]:
        device = self._device(uuid)
        if device is None:
            raise TuningNotFound(f"unknown device {uuid}")
        catalog = self.catalog()
        profile_id = self._match_devices(catalog).get(uuid) or None
        channels = sorted({
            channel.channel_id for channel in device.channels
            if channel.channel_id is not None})
        errors: List[str] = []
        warnings: List[str] = []
        profile = None
        compiled = None
        if profile_id:
            meta = self._profile_meta(catalog, profile_id)
            compiled = profile_engine.compile_profile(meta)
            if channels:
                compiled = profile_engine.expand_channel_entities(
                    compiled, channels)
            errors.extend(compiled.errors)
            warnings.extend(compiled.warnings)
            profile = {
                "id": profile_id,
                "version": meta.version,
                "source": meta.source,
                "hash": meta.digest,
                "requires_engine": meta.requires_engine,
            }

        ability: Dict[str, Any] = {}
        row = self._ability(uuid)
        if row is not None and row.ability_json:
            try:
                parsed = json.loads(row.ability_json)
                if isinstance(parsed, dict):
                    ability = parsed
            except (TypeError, ValueError):
                warnings.append("stored ability document is not valid JSON")

        cache = {
            "roller_shutter": {
                "status": self._safe_rows(
                    self._statuses, uuid, errors, lambda item: {
                        "channel": item.channel,
                        "position": item.position,
                        "state": item.state,
                        "updated_at": self._iso(item.updated_at)}),
                "config": self._safe_rows(
                    self._configs, uuid, errors, lambda item: {
                        "channel": item.channel,
                        "signal_open": item.signal_open,
                        "signal_close": item.signal_close,
                        "payload": self._json_or_none(item.payload_json),
                        "updated_at": self._iso(item.updated_at)}),
                "adjust": self._safe_rows(
                    self._adjusts, uuid, errors, lambda item: {
                        "channel": item.channel,
                        "payload": self._json_or_none(item.payload_json),
                        "updated_at": self._iso(item.updated_at)}),
            },
        }

        polling: List[Dict[str, Any]] = []
        templates: List[Dict[str, Any]] = []
        if compiled is not None:
            polling.extend(
                self._polling_rows(compiled.namespaces, "hub"))
            for template in compiled.subdevices:
                polling.extend(
                    self._polling_rows(template.namespaces, "subdevice"))
                templates.append({
                    "name": template.name,
                    "match": template.match,
                    "entities": self._entity_rows(template.entities),
                })

        return {
            "device": {
                "uuid": device.uuid,
                "name": device.dev_name,
                "type": device.device_type,
                "sub_type": device.sub_type,
                "online": (device.online_status.value
                           if device.online_status is not None else None),
                "last_seen": self._iso(device.last_seen_time),
                "local_ip": device.local_ip,
                "firmware": device.fmware_version,
                "hardware": device.hdware_version,
                "channels": channels,
                "subdevices": [
                    {"id": sub.sub_device_id,
                     "type": sub.sub_device_type,
                     "name": sub.sub_device_name}
                    for sub in device.child_subdevices],
            },
            "profile": profile,
            "ability": ability,
            "entities": (self._entity_rows(compiled.entities)
                         if compiled is not None else []),
            "subdevice_templates": templates,
            "polling": polling,
            "cache": cache,
            "errors": errors,
            "warnings": warnings,
        }

    def simulate(self, profile_id: str, namespace: Optional[str],
                 method: Optional[str], payload: Any,
                 channels: Any = None,
                 subdevice: Any = None) -> Dict[str, Any]:
        catalog = self.catalog()
        if profile_id not in catalog.profiles:
            raise TuningNotFound(f"unknown profile {profile_id}")
        if not isinstance(namespace, str) or not namespace:
            raise TuningError("namespace is required")
        if method not in STATE_METHODS:
            raise TuningError(
                "method must be one of " + ", ".join(STATE_METHODS))
        if not isinstance(payload, dict):
            raise TuningError("payload must be an object")
        channel_list = (self._payload_channels(payload)
                        if channels is None else self._channels(channels))
        compiled = profile_engine.compile_profile(
            self._profile_meta(catalog, profile_id))
        if compiled.errors:
            raise TuningError(
                "profile does not compile: " + "; ".join(compiled.errors))
        expanded = profile_engine.expand_channel_entities(
            compiled, channel_list)
        runtime = profile_engine.DeviceRuntime(profile_id, expanded)
        warnings = list(compiled.warnings)
        template = None
        if subdevice is not None:
            if (not isinstance(subdevice, dict)
                    or not subdevice.get("id")
                    or not subdevice.get("type")):
                raise TuningError("subdevice must contain id and type")
            template = self._match_template(compiled, subdevice["type"])
            if template is None:
                raise TuningError(
                    f"no subdevice template for type "
                    f"{subdevice['type']!r}")
            runtime.add_subdevice(str(subdevice["id"]), template)
        applied = runtime.dispatch(namespace, method, payload)
        declared = set(compiled.namespaces)
        for item in compiled.subdevices:
            declared.update(item.namespaces)
        known = namespace in declared
        if not known:
            warnings.append(
                f"namespace {namespace!r} is not declared by {profile_id}")
        if (template is None and ("id" in payload or "subId" in payload)):
            warnings.append(
                "payload targets a subdevice but no subdevice was provided")
        return {
            "profile_id": profile_id,
            "namespace": namespace,
            "method": method,
            "known_namespace": known,
            "applied": applied,
            "ignored": runtime.ignored,
            "updates": runtime.updates,
            "messages": runtime.messages,
            "entities": {
                key: dict(state.values)
                for key, state in runtime.entities.items() if state.values},
            "subdevices": {
                subdevice_id: {
                    key: dict(state.values)
                    for key, state in item.entities.items() if state.values}
                for subdevice_id, item in runtime.subdevices.items()},
            "errors": list(compiled.errors) + list(runtime.errors),
            "warnings": warnings,
        }

    @staticmethod
    def _channels(channels: Any) -> List[int]:
        if not isinstance(channels, list):
            raise TuningError("channels must be a list")
        result = []
        for channel in channels:
            if (not isinstance(channel, int) or isinstance(channel, bool)
                    or channel < 0 or channel > MAX_SIMULATION_CHANNEL):
                raise TuningError(
                    f"channel must be an integer between 0 and "
                    f"{MAX_SIMULATION_CHANNEL}")
            result.append(channel)
        return result or [0]

    @staticmethod
    def _payload_channels(payload: Dict[str, Any]) -> List[int]:
        found = set()

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                channel = value.get("channel")
                if (isinstance(channel, int)
                        and not isinstance(channel, bool)
                        and 0 <= channel <= MAX_SIMULATION_CHANNEL):
                    found.add(channel)
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(payload)
        return sorted(found) or [0]

    @staticmethod
    def _match_template(compiled, sub_type: Any) -> Any:
        wanted = str(sub_type).strip().lower()
        for template in compiled.subdevices:
            types = template.match.get("type") or []
            if any(str(item).strip().lower() == wanted for item in types):
                return template
        return None

    def read_device(self, uuid: str, namespace: Optional[str] = None,
                    payload: Any = None,
                    timeout: Optional[float] = None) -> Dict[str, Any]:
        device = self._device(uuid)
        if device is None:
            raise TuningNotFound(f"unknown device {uuid}")
        if device.online_status != OnlineStatus.ONLINE:
            raise TuningConflict("device is offline")
        owner = getattr(device, "owner_user", None)
        if owner is None:
            raise TuningConflict("device has no owner account")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise TuningError("payload must be an object")
        catalog = self.catalog()
        profile_id = self._match_devices(catalog).get(uuid)
        if not profile_id:
            raise TuningConflict("no profile matches this device")
        compiled = profile_engine.compile_profile(
            self._profile_meta(catalog, profile_id))
        allowed = dict(compiled.namespaces)
        for template in compiled.subdevices:
            allowed.update(template.namespaces)
        allowed.setdefault(SYSTEM_ALL, None)
        if namespace is None:
            namespace = self._default_namespace(allowed)
        if namespace not in allowed:
            raise TuningError(
                f"namespace {namespace!r} is not declared by {profile_id}")
        timeout = self._clamp_timeout(timeout)
        now = self._clock()
        with self._read_lock:
            last = self._last_read.get(uuid)
            if last is not None and now - last < self._read_cooldown:
                raise TuningRateLimited(
                    "wait before reading this device again",
                    self._read_cooldown - (now - last))
            self._last_read[uuid] = now
        result = self._probe_client().read(
            uuid, owner, namespace, payload, timeout)
        result["profile_id"] = profile_id
        result["typed"] = self._typed_values(device, compiled, result)
        return result

    def _runtime_for(self, compiled, device) -> Any:
        runtime = profile_engine.DeviceRuntime(device.uuid, compiled)
        for subdevice in device.child_subdevices:
            template = self._match_template(
                compiled, subdevice.sub_device_type)
            if template is not None:
                runtime.add_subdevice(
                    str(subdevice.sub_device_id), template)
        return runtime

    def _typed_values(self, device, compiled,
                      response: Dict[str, Any]) -> Dict[str, Any]:
        if response.get("method") not in STATE_METHODS:
            return {"applied": 0, "entities": {}, "subdevices": {},
                    "errors": []}
        channels = sorted({
            channel.channel_id for channel in device.channels
            if channel.channel_id is not None})
        expanded = (profile_engine.expand_channel_entities(compiled, channels)
                    if channels else compiled)
        runtime = self._runtime_for(expanded, device)
        applied = runtime.dispatch(
            response.get("namespace"), response.get("method"),
            response.get("payload") or {})
        return {
            "applied": applied,
            "entities": {
                key: dict(state.values)
                for key, state in runtime.entities.items() if state.values},
            "subdevices": {
                subdevice_id: {
                    key: dict(state.values)
                    for key, state in item.entities.items() if state.values}
                for subdevice_id, item in runtime.subdevices.items()},
            "errors": list(runtime.errors),
        }

    @staticmethod
    def _default_namespace(allowed) -> str:
        getters = sorted(
            name for name, spec in allowed.items()
            if spec is not None and "GET" in spec.methods)
        return getters[0] if getters else SYSTEM_ALL

    def _clamp_timeout(self, timeout: Optional[float]) -> float:
        if timeout is None:
            return self._read_timeout
        try:
            value = float(timeout)
        except (TypeError, ValueError) as error:
            raise TuningError("timeout must be a number") from error
        return max(0.5, min(value, READ_TIMEOUT_MAX))

    def _probe_client(self) -> MqttProbe:
        if self._probe is None:
            self._probe = MqttProbe(
                host=os.environ.get("TUNING_MQTT_HOST", "localhost"),
                port=int(os.environ.get("TUNING_MQTT_PORT", "2001")),
                ca=os.environ.get("TUNING_MQTT_CA",
                                  "/data/mqtt/certs/ca.crt"))
        return self._probe

    def refresh_ability(self, uuid: str,
                        actor: str = "unknown") -> Dict[str, Any]:
        """Ask the device for its ability document as an app identity."""
        device = self._device(uuid)
        if device is None:
            raise TuningNotFound(f"unknown device {uuid}")
        if device.online_status != OnlineStatus.ONLINE:
            raise TuningConflict("device is offline")
        owner = getattr(device, "owner_user", None)
        if owner is None:
            raise TuningConflict("device has no owner account")
        now = self._clock()
        with self._ability_lock:
            last = self._last_ability.get(uuid)
            if last is not None and now - last < self._read_cooldown:
                raise TuningRateLimited(
                    "wait before refreshing the ability again",
                    self._read_cooldown - (now - last))
            self._last_ability[uuid] = now
        response = self._probe_client().send(
            uuid, owner, "GET", SYSTEM_ABILITY, {}, self._read_timeout)
        if response.get("method") == "ERROR":
            raise TuningError("device rejected the ability request")
        payload = response.get("payload") or {}
        ability = (payload.get("ability", payload)
                   if isinstance(payload, dict) else {})
        if not isinstance(ability, dict) or not ability:
            raise TuningError("device returned an empty ability document")
        self._set_ability(device_uuid=uuid, ability=ability)
        self._audit({
            "action": "device.ability",
            "device_uuid": uuid,
            "actor": actor,
            "namespaces": len(ability),
        })
        return {
            "uuid": uuid,
            "count": len(ability),
            "namespaces": sorted(ability),
        }

    # -- V2 typed commands ---------------------------------------------
    @staticmethod
    def _scan_tokens(value: Any, found: set) -> None:
        if isinstance(value, str):
            if value in ("$channel", "$value"):
                found.add(value)
        elif isinstance(value, dict):
            for item in value.values():
                TuningStore._scan_tokens(item, found)
        elif isinstance(value, list):
            for item in value:
                TuningStore._scan_tokens(item, found)

    def _device_compiled(self, uuid: str):
        device = self._device(uuid)
        if device is None:
            raise TuningNotFound(f"unknown device {uuid}")
        catalog = self.catalog()
        profile_id = self._match_devices(catalog).get(uuid) or None
        channels = sorted({
            channel.channel_id for channel in device.channels
            if channel.channel_id is not None})
        compiled = None
        if profile_id:
            compiled = profile_engine.compile_profile(
                self._profile_meta(catalog, profile_id))
            if channels:
                compiled = profile_engine.expand_channel_entities(
                    compiled, channels)
        return device, profile_id, compiled, channels

    def _command_rows(self, compiled, device) -> List[Dict[str, Any]]:
        rows = []
        device_channels = sorted({
            channel.channel_id for channel in device.channels
            if channel.channel_id is not None})
        for entity in compiled.entities.values():
            for key, spec in entity.commands.items():
                tokens: set = set()
                self._scan_tokens(spec.payload, tokens)
                accepts_value = "$value" in tokens
                accepts_channel = "$channel" in tokens
                if entity.channel is not None:
                    channels = [entity.channel]
                elif accepts_channel:
                    channels = device_channels
                else:
                    channels = []
                rows.append({
                    "id": f"{entity.key}.{key}",
                    "entity": entity.key,
                    "name": entity.name,
                    "platform": entity.platform,
                    "command": key,
                    "namespace": spec.namespace,
                    "type": "number" if accepts_value else "action",
                    "unit": entity.unit,
                    "min": entity.min_value,
                    "max": entity.max_value,
                    "step": entity.step,
                    "value_scale": spec.value_scale,
                    "accepts_value": accepts_value,
                    "accepts_channel": accepts_channel,
                    "channels": channels,
                    "channel": (channels[0] if len(channels) == 1 else None),
                    "payload_template": spec.payload,
                })
        return sorted(rows, key=lambda row: row["id"])

    def device_commands(self, uuid: str) -> Dict[str, Any]:
        device, profile_id, compiled, _channels = self._device_compiled(uuid)
        if not profile_id or compiled is None:
            raise TuningConflict("no profile matches this device")
        rows = self._command_rows(compiled, device)
        return {
            "uuid": uuid,
            "profile_id": profile_id,
            "online": (device.online_status.value
                       if device.online_status is not None else None),
            "commands": rows,
            "namespaces": sorted({row["namespace"] for row in rows}),
            "warnings": list(compiled.warnings),
        }

    def _cache_snapshot(self, uuid: str) -> Dict[str, Any]:
        statuses = self._safe_rows(
            self._statuses, uuid, [], lambda item: item)
        configs = self._safe_rows(
            self._configs, uuid, [], lambda item: item)
        adjusts = self._safe_rows(
            self._adjusts, uuid, [], lambda item: item)
        return {
            "status": [
                {"channel": item.channel, "position": item.position,
                 "state": item.state,
                 "updated_at": self._iso(item.updated_at)}
                for item in statuses],
            "config": [
                {"channel": item.channel, "signal_open": item.signal_open,
                 "signal_close": item.signal_close,
                 "payload": self._json_or_none(item.payload_json),
                 "updated_at": self._iso(item.updated_at)}
                for item in configs],
            "adjust": [
                {"channel": item.channel,
                 "payload": self._json_or_none(item.payload_json),
                 "updated_at": self._iso(item.updated_at)}
                for item in adjusts],
        }

    def execute_command(self, uuid: str, command_id: str,
                        channel: Any = None, value: Any = None,
                        confirm: bool = False,
                        token: Optional[str] = None,
                        actor: str = "unknown") -> Dict[str, Any]:
        if not isinstance(command_id, str) or not command_id:
            raise TuningError("command id is required")
        if confirm:
            return self._run_command(uuid, command_id, token, actor)
        return self._prepare_command(uuid, command_id, channel, value, actor)

    def _prepare_command(self, uuid: str, command_id: str, channel: Any,
                         value: Any, actor: str) -> Dict[str, Any]:
        device, profile_id, compiled, _channels = self._device_compiled(uuid)
        if device.online_status != OnlineStatus.ONLINE:
            raise TuningConflict("device is offline")
        if getattr(device, "owner_user", None) is None:
            raise TuningConflict("device has no owner account")
        if not profile_id or compiled is None:
            raise TuningConflict("no profile matches this device")
        rows = self._command_rows(compiled, device)
        row = next((item for item in rows if item["id"] == command_id), None)
        if row is None:
            raise TuningError(f"unknown command {command_id!r}")
        selected_channel = self._command_channel(row, channel)
        scaled_value = self._command_value(row, value)
        values = {}
        if row["accepts_channel"]:
            values["channel"] = selected_channel
        if row["accepts_value"]:
            values["value"] = scaled_value
        try:
            payload = profile_engine.substitute(
                row["payload_template"], values)
        except Exception as error:  # noqa: BLE001 - token failures are content
            raise TuningError(
                "command payload cannot be built") from error
        now = self._clock()
        with self._command_lock:
            last = self._last_command.get(uuid)
            if last is not None and now - last < self._command_cooldown:
                raise TuningRateLimited(
                    "wait before sending another command",
                    self._command_cooldown - (now - last))
            self._last_command[uuid] = now
            self._prune_tokens(now)
            token_id = secrets.token_urlsafe(24)
            self._command_tokens[token_id] = {
                "device_uuid": uuid,
                "profile_id": profile_id,
                "command_id": command_id,
                "namespace": row["namespace"],
                "payload": payload,
                "channel": selected_channel,
                "value": value,
                "actor": actor,
                "expires_at": now + self._command_token_ttl,
            }
        return {
            "requires_confirmation": True,
            "token": token_id,
            "expires_in": int(self._command_token_ttl),
            "device_uuid": uuid,
            "profile_id": profile_id,
            "command": {
                "id": command_id,
                "namespace": row["namespace"],
                "channel": selected_channel,
                "value": value,
                "payload": payload,
            },
        }

    @staticmethod
    def _command_channel(row: Dict[str, Any], channel: Any) -> Any:
        if not row["accepts_channel"]:
            return None
        channels = row["channels"]
        if channel is None:
            if len(channels) == 1:
                return channels[0]
            raise TuningError("channel is required for this command")
        if (not isinstance(channel, int) or isinstance(channel, bool)
                or channel not in channels):
            raise TuningError(f"channel must be one of {channels}")
        return channel

    @staticmethod
    def _command_value(row: Dict[str, Any], value: Any) -> Any:
        if not row["accepts_value"]:
            return None
        if (not isinstance(value, (int, float))
                or isinstance(value, bool)):
            raise TuningError("value must be a number")
        minimum = row.get("min")
        maximum = row.get("max")
        if minimum is not None and value < minimum:
            raise TuningError(f"value must be at least {minimum}")
        if maximum is not None and value > maximum:
            raise TuningError(f"value must be at most {maximum}")
        scale = row.get("value_scale")
        scaled = value * scale if scale is not None else value
        if isinstance(scaled, float) and scaled.is_integer():
            scaled = int(scaled)
        return scaled

    def _prune_tokens(self, now: float) -> None:
        for key in [
                key for key, item in self._command_tokens.items()
                if item["expires_at"] <= now]:
            self._command_tokens.pop(key, None)

    def _run_command(self, uuid: str, command_id: str,
                     token: Optional[str], actor: str) -> Dict[str, Any]:
        if not isinstance(token, str) or not token:
            raise TuningError("confirmation token is required")
        now = self._clock()
        with self._command_lock:
            entry = self._command_tokens.get(token)
            if entry is None:
                raise TuningConflict(
                    "confirmation expired or already used; request a new one")
            if (entry["device_uuid"] != uuid
                    or entry["command_id"] != command_id):
                raise TuningConflict(
                    "confirmation does not match this command")
            if entry["expires_at"] <= now:
                self._command_tokens.pop(token, None)
                raise TuningConflict(
                    "confirmation expired; request a new one")
            if uuid in self._busy_devices:
                raise TuningConflict("another command is in progress")
            self._command_tokens.pop(token, None)
            self._busy_devices.add(uuid)
        before = self._cache_snapshot(uuid)
        result: Dict[str, Any] = {}
        failure: Optional[Exception] = None
        error: Optional[str] = None
        try:
            device = self._device(uuid)
            if device is None:
                raise TuningNotFound(f"unknown device {uuid}")
            if device.online_status != OnlineStatus.ONLINE:
                raise TuningConflict("device is offline")
            owner = getattr(device, "owner_user", None)
            if owner is None:
                raise TuningConflict("device has no owner account")
            response = self._probe_client().send(
                uuid, owner, "SET", entry["namespace"],
                entry["payload"], self._read_timeout)
            result = {
                "ok": response.get("ok"),
                "method": response.get("method"),
                "header": response.get("header"),
                "payload": response.get("payload"),
                "elapsed_ms": response.get("elapsed_ms"),
                "received_at": response.get("received_at"),
            }
            if not result["ok"]:
                error = f"device rejected the command ({result['method']})"
        except TuningError as failure_error:
            failure = failure_error
            error = str(failure_error)
            result = {"ok": False, "error": error}
        except Exception as failure_error:  # noqa: BLE001 - reported, then raised
            failure = TuningUnavailable("live command failed")
            error = str(failure)
            result = {"ok": False, "error": error}
        finally:
            with self._command_lock:
                self._busy_devices.discard(uuid)
        after = self._cache_snapshot(uuid)
        self._audit({
            "action": "device.command",
            "device_uuid": uuid,
            "profile_id": entry.get("profile_id"),
            "actor": (actor if actor != "unknown"
                      else entry.get("actor")),
            "command": command_id,
            "namespace": entry["namespace"],
            "channel": entry.get("channel"),
            "value": entry.get("value"),
            "payload": entry["payload"],
            "ok": not error,
            "error": error,
            "before": before,
            "after": after,
        })
        if failure is not None:
            raise failure
        return {
            "ok": not error,
            "error": error,
            "command": {
                "id": command_id,
                "namespace": entry["namespace"],
                "channel": entry.get("channel"),
                "value": entry.get("value"),
                "payload": entry["payload"],
            },
            "result": result,
            "before": before,
            "after": after,
            "profile_id": entry.get("profile_id"),
        }

    # -- validation ----------------------------------------------------
    def validate(self, text: str, profile_id: Optional[str] = None,
                 filename: str = "profile.yaml") -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        data = None
        if not isinstance(text, str) or not text.strip():
            errors.append("empty YAML document")
        elif len(text.encode("utf-8")) > MAX_YAML_BYTES:
            errors.append(f"YAML exceeds {MAX_YAML_BYTES} bytes")
        elif len(text.splitlines()) > MAX_YAML_LINES:
            errors.append(f"YAML exceeds {MAX_YAML_LINES} lines")
        else:
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as error:
                mark = getattr(error, "problem_mark", None)
                location = (f"line {mark.line + 1}, column "
                            f"{mark.column + 1}" if mark else "unknown")
                errors.append(f"YAML parse error ({location}): {error}")
        if data is not None and not errors:
            if not isinstance(data, dict):
                errors.append("profile must be a YAML object")
            elif _depth(data) > MAX_DEPTH:
                errors.append(f"YAML is deeper than {MAX_DEPTH} levels")
            else:
                found_id = (data.get("profile") or {}).get("id")
                if profile_id is not None and found_id != profile_id:
                    errors.append(
                        f"profile id {found_id!r} does not match "
                        f"{profile_id!r}")
                lint_errors, warnings = lint_documents(
                    [(filename, data)], self._validator)
                errors.extend(lint_errors)
                if not errors:
                    meta = profile_engine.ProfileMeta(
                        id=found_id,
                        version=(data.get("profile") or {}).get("version"),
                        source="preview",
                        digest=None,
                        requires_engine=None,
                        data=data,
                    )
                    compiled = profile_engine.compile_profile(meta)
                    errors.extend(compiled.errors)
                    warnings.extend(compiled.warnings)
        summary: Dict[str, Any] = {}
        diff = ""
        diff_base: Optional[str] = None
        if data is not None and isinstance(data, dict):
            profile = data.get("profile") or {}
            summary = {
                "id": profile.get("id"),
                "version": profile.get("version"),
                "requires_engine": profile.get("requires_engine"),
                "entities": self._entity_summary(data),
            }
            found_id = profile.get("id")
            if isinstance(found_id, str) and found_id:
                diff_base, base_text = self._diff_base(found_id)
                diff = self._diff(
                    base_text, text,
                    f"{found_id}.yaml ({diff_base})",
                    f"{found_id}.yaml (proposal)")
        return ValidationResult(
            valid=not errors,
            profile_id=summary.get("id"),
            errors=errors,
            warnings=warnings,
            summary=summary,
            data=data,
            diff=diff,
            diff_base=diff_base,
        )

    def _diff_base(self, profile_id: str) -> Tuple[str, str]:
        override = self._override_path(profile_id)
        if override is not None:
            return "override", override.read_text()
        bundled = self._bundled_path(profile_id)
        if bundled is not None:
            return "bundled", bundled.read_text()
        return "none", ""

    @staticmethod
    def _entity_summary(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        entities = []
        for entity in data.get("entities") or []:
            if isinstance(entity, dict):
                entities.append({
                    "key": entity.get("key"),
                    "platform": entity.get("platform"),
                    "name": entity.get("name"),
                    "channel": entity.get("channel"),
                })
        return entities

    # -- writes --------------------------------------------------------
    def save_override(self, profile_id: str, text: str,
                      expected_hash: Optional[str] = None,
                      actor: str = "unknown") -> Dict[str, Any]:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            raise TuningError("invalid profile id")
        result = self.validate(text, profile_id=profile_id)
        if not result.valid:
            raise TuningError("; ".join(result.errors))
        current = self._current_hash(profile_id)
        if expected_hash is not None and expected_hash != current:
            raise TuningConflict(
                "profile changed since it was loaded; refresh before saving")
        override = (self._override_path(profile_id)
                    or self.overrides / f"{profile_id}.yaml")
        before = override.read_text() if override.exists() else None
        self._backup_override(profile_id, override)
        content = text if text.endswith("\n") else text + "\n"
        self._atomic_write(override, content)
        revision = self._reload()
        diff = self._diff(
            self._bundled_text(profile_id), content,
            f"{profile_id}.yaml (bundled)", f"{profile_id}.yaml (override)")
        self._audit({
            "action": "override.save",
            "profile_id": profile_id,
            "actor": actor,
            "before_hash": _hash_text(before) if before is not None else current,
            "after_hash": _hash_text(content),
            "revision": revision,
        })
        return {
            "id": profile_id,
            "revision": revision,
            "override_hash": _hash_text(content),
            "diff": diff,
            "warnings": result.warnings,
        }

    def delete_override(self, profile_id: str,
                        expected_hash: Optional[str] = None,
                        actor: str = "unknown") -> Dict[str, Any]:
        override = self._override_path(profile_id)
        if override is None:
            raise TuningNotFound(f"no override for {profile_id}")
        current = _hash_text(override.read_text())
        if expected_hash is not None and expected_hash != current:
            raise TuningConflict(
                "profile changed since it was loaded; refresh before deleting")
        before = override.read_text()
        self._backup_override(profile_id, override)
        override.unlink()
        revision = self._reload()
        self._audit({
            "action": "override.delete",
            "profile_id": profile_id,
            "actor": actor,
            "before_hash": _hash_text(before),
            "after_hash": None,
            "revision": revision,
        })
        return {"id": profile_id, "revision": revision,
                "removed": True}

    # -- backups -------------------------------------------------------
    def list_backups(self, profile_id: str) -> List[Dict[str, Any]]:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            return []
        items = []
        for path in self.backups.glob(f"*-{profile_id}.yaml"):
            stat = path.stat()
            items.append({
                "file": path.name,
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc).isoformat(),
                "hash": _hash_text(path.read_text()),
            })
        return sorted(items, key=lambda item: item["created_at"],
                      reverse=True)

    def restore_backup(self, profile_id: str, filename: str,
                       actor: str = "unknown") -> Dict[str, Any]:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            raise TuningError("invalid profile id")
        source = self.backups / filename
        if source.parent != self.backups or not source.is_file():
            raise TuningNotFound(f"unknown backup {filename}")
        if not filename.endswith(f"-{profile_id}.yaml"):
            raise TuningError("backup does not belong to this profile")
        text = source.read_text()
        result = self.validate(text, profile_id=profile_id)
        if not result.valid:
            raise TuningConflict(
                "backup no longer validates: " + "; ".join(result.errors))
        override = (self._override_path(profile_id)
                    or self.overrides / f"{profile_id}.yaml")
        self._backup_override(profile_id, override)
        self._atomic_write(override, text)
        revision = self._reload()
        self._audit({
            "action": "override.restore",
            "profile_id": profile_id,
            "actor": actor,
            "backup": filename,
            "after_hash": _hash_text(text),
            "revision": revision,
        })
        return {"id": profile_id, "revision": revision,
                "restored": filename}

    # -- import / export ----------------------------------------------
    @staticmethod
    def _export_source(source: str) -> str:
        normalized = (source or "effective").strip().lower()
        if normalized in ("override", "overrides"):
            return "overrides"
        if normalized in ("effective", "bundled", "catalog"):
            return "effective"
        raise TuningError(
            "source must be 'overrides' or 'effective'")

    def export_yaml(self, profile_id: Optional[str] = None,
                    source: str = "effective") -> Tuple[str, str]:
        """Return (filename, YAML text)."""
        if profile_id is None:
            raise TuningError("profile_id is required for YAML export")
        if not PROFILE_ID_RE.fullmatch(profile_id):
            raise TuningError("invalid profile id")
        if self._export_source(source) == "overrides":
            override = self._override_path(profile_id)
            if override is None:
                raise TuningNotFound(f"no override for {profile_id}")
            return f"{profile_id}.yaml", override.read_text()
        profile = self.get_profile(profile_id)
        return f"{profile_id}.yaml", profile["yaml"]

    def export_zip(self, source: str = "overrides") -> Tuple[str, bytes]:
        source = self._export_source(source)
        entries = {}
        if source == "overrides":
            for profile_id in sorted(self._override_ids()):
                override = self._override_path(profile_id)
                if override is not None:
                    entries[f"{profile_id}.yaml"] = override.read_text()
        else:
            catalog = self.catalog()
            for profile_id in sorted(catalog.profiles)[:MAX_EXPORT_PROFILES]:
                entries[f"{profile_id}.yaml"] = _yaml_text(
                    catalog.profiles[profile_id])
        if not entries:
            raise TuningNotFound("nothing to export")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                "revision": self.catalog().revision,
                "source": source,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "profiles": [
                    {"id": name[:-5], "hash": _hash_text(text)}
                    for name, text in entries.items()
                ],
            }
            archive.writestr("manifest.json", json.dumps(
                manifest, indent=2, sort_keys=True) + "\n")
            for name, text in entries.items():
                archive.writestr(name, text)
        return "meross-profiles.zip", buffer.getvalue()

    def import_profiles(self, files: Iterable[Tuple[str, str]],
                        dry_run: bool = True,
                        actor: str = "unknown") -> Dict[str, Any]:
        validated = []
        seen = set()
        for filename, text in files:
            result = self.validate(text, filename=filename or "profile.yaml")
            if not result.valid:
                raise TuningError(
                    f"{filename}: " + "; ".join(result.errors))
            profile_id = result.profile_id
            if not profile_id or not PROFILE_ID_RE.fullmatch(profile_id):
                raise TuningError(f"{filename}: invalid profile id")
            if profile_id in seen:
                raise TuningError(f"{filename}: duplicate profile id")
            seen.add(profile_id)
            validated.append((profile_id, filename, text, result))
        if not dry_run:
            for profile_id, _filename, text, _result in validated:
                override = (self._override_path(profile_id)
                            or self.overrides / f"{profile_id}.yaml")
                self._backup_override(profile_id, override)
                self._atomic_write(override,
                                   text if text.endswith("\n")
                                   else text + "\n")
                self._audit({
                    "action": "override.import",
                    "profile_id": profile_id,
                    "actor": actor,
                    "after_hash": _hash_text(text),
                })
            revision = self._reload()
        else:
            revision = self.catalog().revision
        return {
            "dry_run": dry_run,
            "revision": revision,
            "profiles": [
                {"id": profile_id, "filename": filename,
                 "warnings": result.warnings}
                for profile_id, filename, _text, result in validated
            ],
        }

    # -- audit ---------------------------------------------------------
    def audit_entries(self, limit: int = 200,
                      profile_id: Optional[str] = None,
                      device_uuid: Optional[str] = None
                      ) -> List[Dict[str, Any]]:
        if not self.audit.is_file():
            return []
        entries = []
        with self.audit.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if profile_id and entry.get("profile_id") != profile_id:
                    continue
                if device_uuid and entry.get("device_uuid") != device_uuid:
                    continue
                entries.append(entry)
        return entries[-max(1, min(limit, 500)):][::-1]

    def _audit(self, entry: Dict[str, Any]) -> None:
        entry = dict(entry)
        entry["at"] = datetime.now(timezone.utc).isoformat()
        try:
            self.audit.parent.mkdir(parents=True, exist_ok=True)
            with self.audit.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
            os.chmod(self.audit, 0o600)
        except OSError:
            pass

    # -- filesystem helpers -------------------------------------------
    def _current_hash(self, profile_id: str) -> Optional[str]:
        override = self._override_path(profile_id)
        if override is not None:
            return _hash_text(override.read_text())
        catalog = self.catalog()
        hashes = catalog.profile_hashes()
        return hashes.get(profile_id)

    def _override_ids(self) -> List[str]:
        ids = []
        for path in self._iter_override_files():
            try:
                data = yaml.safe_load(path.read_text())
            except (OSError, yaml.YAMLError):
                continue
            profile_id = ((data or {}).get("profile") or {}).get("id")
            if isinstance(profile_id, str):
                ids.append(profile_id)
        return ids

    def _iter_override_files(self) -> Iterable[Path]:
        try:
            for path in sorted(self.overrides.iterdir()):
                if path.is_file() and path.suffix in (".yaml", ".yml"):
                    yield path
        except OSError:
            return

    def _override_path(self, profile_id: str) -> Optional[Path]:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            return None
        for path in self._iter_override_files():
            try:
                data = yaml.safe_load(path.read_text())
            except (OSError, yaml.YAMLError):
                continue
            found = ((data or {}).get("profile") or {}).get("id")
            if found == profile_id:
                return path
        return None

    def _bundled_path(self, profile_id: str) -> Optional[Path]:
        catalog = self.catalog()
        for path in Path(catalog.directory).iterdir():
            if path.suffix not in (".yaml", ".yml"):
                continue
            try:
                data = yaml.safe_load(path.read_text())
            except (OSError, yaml.YAMLError):
                continue
            if ((data or {}).get("profile") or {}).get("id") == profile_id:
                return path
        return None

    def _bundled_text(self, profile_id: str) -> str:
        path = self._bundled_path(profile_id)
        if path is not None:
            return path.read_text()
        data = self.catalog().profiles.get(profile_id)
        return _yaml_text(data) if data else ""

    def _backup_override(self, profile_id: str,
                         override: Optional[Path]) -> None:
        if override is None or not override.is_file():
            return
        self.backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = self.backups / f"{stamp}-{profile_id}.yaml"
        shutil.copyfile(override, target)
        os.chmod(target, 0o600)
        backups = sorted(
            self.backups.glob(f"*-{profile_id}.yaml"))
        for old in backups[:-MAX_BACKUPS_PER_PROFILE]:
            try:
                old.unlink()
            except OSError:
                pass

    @staticmethod
    def _atomic_write(target: Path, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            dir=target.parent, prefix=f".{target.name}.")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def _reload(self) -> str:
        result = self._catalog_reloader() or {}
        return result.get("revision") or self.catalog().revision

    @staticmethod
    def _diff(before: str, after: str, before_name: str,
              after_name: str) -> str:
        return "\n".join(difflib.unified_diff(
            before.splitlines(), after.splitlines(),
            fromfile=before_name, tofile=after_name, lineterm=""))


_store: Optional[TuningStore] = None


def get_tuning_store() -> TuningStore:
    global _store
    if _store is None:
        _store = TuningStore()
    return _store
