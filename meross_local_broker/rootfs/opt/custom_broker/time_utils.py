# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""UTC datetime helpers and SQLAlchemy storage type.

SQLite does not preserve timezone information.  The broker therefore stores
naive UTC values in the database and exposes timezone-aware UTC datetimes to
the application.  All new code must use :func:`utcnow` instead of
``datetime.now()`` or ``datetime.utcnow()``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.types import DateTime, TypeDecorator

UTC = timezone.utc


def utcnow() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(UTC)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Return ``value`` as an aware UTC datetime.

    Naive values are assumed to be UTC for compatibility with databases
    written before the UTC migration.  ``None`` is preserved.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_epoch(value: Optional[datetime]) -> Optional[float]:
    """Convert a datetime to Unix epoch seconds, treating naive values as UTC."""
    value = as_utc(value)
    return value.timestamp() if value is not None else None


def utc_iso(value: Optional[datetime]) -> Optional[str]:
    """Serialize a datetime as ISO 8601 with a ``Z`` UTC suffix."""
    if value is None:
        return None
    if not isinstance(value, datetime):
        return value
    return as_utc(value).isoformat().replace("+00:00", "Z")


class UTCDateTime(TypeDecorator):
    """Store naive UTC in SQLite and return aware UTC to the application."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[datetime]:
        if value is None:
            return None
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: Any, dialect: Any) -> Optional[datetime]:
        if value is None:
            return None
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
