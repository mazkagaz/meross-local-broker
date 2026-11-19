# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Signature, freshness and replay checks for device MQTT publications.

The default mode is observation: mismatches are logged but still processed.
Set MQTT_INTEGRITY_MODE=enforce once device compatibility is confirmed.
"""
from hashlib import md5
import hmac
import os
import time
from typing import Optional, Tuple

from expiringdict import ExpiringDict

MODE = os.getenv("MQTT_INTEGRITY_MODE", "observe").strip().lower()
if MODE not in {"observe", "enforce"}:
    MODE = "observe"

try:
    MAX_SKEW_SECONDS = max(60, int(os.getenv("MQTT_MAX_SKEW_SECONDS", "900")))
except ValueError:
    MAX_SKEW_SECONDS = 900

_REPLAY_CACHE = ExpiringDict(max_age_seconds=max(MAX_SKEW_SECONDS * 2, 60),
                             max_len=50000)
_LAST_LOG = ExpiringDict(max_age_seconds=300, max_len=5000)


def enforced() -> bool:
    return MODE == "enforce"


def reset_cache() -> None:
    _REPLAY_CACHE.clear()
    _LAST_LOG.clear()


def _timestamp_seconds(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    # Some firmwares report milliseconds.
    if timestamp > 10 ** 12:
        timestamp //= 1000
    return timestamp


def evaluate(device_uuid: str, payload, dev_key: str,
             now: Optional[int] = None) -> Tuple[bool, str]:
    header = payload.get("header") if isinstance(payload, dict) else None
    if not isinstance(header, dict):
        return False, "missing_header"

    signature = header.get("sign")
    message_id = header.get("messageId")
    raw_timestamp = header.get("timestamp")
    timestamp = _timestamp_seconds(raw_timestamp)
    if not isinstance(signature, str) or not isinstance(message_id, str) or not message_id:
        return False, "missing_signature_fields"
    if timestamp is None or isinstance(raw_timestamp, bool):
        return False, "invalid_timestamp"
    if not isinstance(dev_key, str) or not dev_key:
        return False, "missing_device_key"

    # Devices sign the timestamp exactly as sent (seconds or milliseconds).
    expected = md5(f"{message_id}{dev_key}{raw_timestamp}".encode("utf8")).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        return False, "invalid_signature"

    current = int(time.time()) if now is None else int(now)
    if abs(current - timestamp) > MAX_SKEW_SECONDS:
        return False, "stale_timestamp"

    replay_key = f"{device_uuid}:{message_id}:{signature.lower()}"
    if replay_key in _REPLAY_CACHE:
        return False, "replay"
    _REPLAY_CACHE[replay_key] = True
    return True, ""


def should_log(device_uuid: str, reason: str) -> bool:
    """Rate-limits one warning per device/reason per five minutes."""
    key = f"{device_uuid}:{reason}"
    if key in _LAST_LOG:
        return False
    _LAST_LOG[key] = True
    return True
