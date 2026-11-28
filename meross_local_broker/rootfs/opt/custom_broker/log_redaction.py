# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Redact sensitive values from broker log records.

Pseudonyms are stable for the lifetime of the installation key and are not
reversible, so logs can be pasted into an issue without manual masking.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets

_UUID_RE = re.compile(r"\b[0-9a-fA-F]{32}\b")
_MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_APP_TOPIC_RE = re.compile(r"(/app/\d+)-([A-Za-z0-9]+)(/subscribe)")
_JSON_SECRET_RE = re.compile(
    r'(?i)("(?:sign|key|token|mqttkey|password)"\s*:\s*)"[^"]*"')
_BASIC_RE = re.compile(r"(?i)(Basic\s+)[A-Za-z0-9_\-]+")
_SAFE_IPS = {"127.0.0.1", "0.0.0.0", "255.255.255.255"}
_SECRET_PATH = "/data/log_redaction.key"


def _load_secret() -> bytes:
    try:
        with open(_SECRET_PATH, "rb") as handle:
            value = handle.read(32)
        if len(value) == 32:
            return value
    except OSError:
        pass
    value = secrets.token_bytes(32)
    try:
        with open(_SECRET_PATH, "wb") as handle:
            handle.write(value)
        os.chmod(_SECRET_PATH, 0o600)
    except OSError:
        pass
    return value


class Redactor:
    def __init__(self, secret: bytes):
        self._secret = secret

    def _alias(self, prefix: str, value: str) -> str:
        digest = hmac.new(
            self._secret, value.encode("utf8"), hashlib.sha256).hexdigest()
        return f"{prefix}-{digest[:8]}"

    def _redact_ip(self, match: re.Match) -> str:
        value = match.group(0)
        return value if value in _SAFE_IPS else self._alias("ip", value)

    def redact(self, text: str) -> str:
        if not text:
            return text
        text = _JSON_SECRET_RE.sub(r'\1"***"', text)
        text = _BASIC_RE.sub(r"\1***", text)
        text = _APP_TOPIC_RE.sub(
            lambda m: f"{m.group(1)}-{self._alias('app', m.group(2))}"
                      f"{m.group(3)}", text)
        text = _MAC_RE.sub(lambda m: self._alias("mac", m.group(0)), text)
        text = _IPV4_RE.sub(self._redact_ip, text)
        text = _EMAIL_RE.sub(lambda m: self._alias("user", m.group(0)), text)
        text = _UUID_RE.sub(lambda m: self._alias("uuid", m.group(0)), text)
        return text


def _redact_args(redactor: Redactor, value):
    if isinstance(value, str):
        return redactor.redact(value)
    if isinstance(value, tuple):
        return tuple(_redact_args(redactor, item) for item in value)
    if isinstance(value, dict):
        return {key: _redact_args(redactor, item)
                for key, item in value.items()}
    return value


class RedactionFilter(logging.Filter):
    def __init__(self, redactor: Redactor):
        super().__init__()
        self._redactor = redactor

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redactor.redact(record.msg)
        if record.args:
            record.args = _redact_args(self._redactor, record.args)
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = self._redactor.redact(record.exc_text)
        if record.stack_info:
            record.stack_info = self._redactor.redact(record.stack_info)
        return True


_REDACTOR = Redactor(_load_secret())


def install_filter(logger: logging.Logger) -> None:
    if any(isinstance(item, RedactionFilter) for item in logger.filters):
        return
    logger.addFilter(RedactionFilter(_REDACTOR))


def redact_text(text: str) -> str:
    """Redact identifiers and secrets from a string."""
    return _REDACTOR.redact(text)


def install_handlers(handlers) -> None:
    for handler in handlers:
        if not any(isinstance(item, RedactionFilter)
                   for item in handler.filters):
            handler.addFilter(RedactionFilter(_REDACTOR))
