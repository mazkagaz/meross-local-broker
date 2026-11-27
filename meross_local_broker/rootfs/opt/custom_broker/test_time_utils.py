# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Tests for UTC helpers and the SQLite UTC datetime type."""
from datetime import datetime, timedelta, timezone
import unittest

from sqlalchemy import Column, Integer, MetaData, Table, create_engine

from time_utils import UTCDateTime, as_utc, to_epoch, utc_iso, utcnow

UTC = timezone.utc


class UtcHelpersTest(unittest.TestCase):
    def test_utcnow_is_aware_utc(self):
        now = utcnow()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset(), timedelta(0))

    def test_naive_values_are_read_as_utc(self):
        naive = datetime(2026, 11, 22, 10, 0)
        aware = as_utc(naive)
        self.assertEqual(aware, datetime(2026, 11, 22, 10, 0, tzinfo=UTC))

    def test_non_utc_values_are_converted(self):
        plus_two = timezone(timedelta(hours=2))
        aware = as_utc(datetime(2026, 11, 22, 12, 0, tzinfo=plus_two))
        self.assertEqual(aware, datetime(2026, 11, 22, 10, 0, tzinfo=UTC))

    def test_epoch_treats_naive_as_utc(self):
        naive = datetime(2026, 11, 22, 10, 0)
        self.assertEqual(to_epoch(naive), to_epoch(naive.replace(tzinfo=UTC)))

    def test_iso_uses_z_suffix(self):
        self.assertEqual(
            utc_iso(datetime(2026, 11, 22, 10, 0)),
            "2026-11-22T10:00:00Z")
        self.assertIsNone(utc_iso(None))


class UtcDateTimeTypeTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.metadata = MetaData()
        self.table = Table(
            "timestamps", self.metadata,
            Column("id", Integer, primary_key=True),
            Column("at", UTCDateTime))
        self.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_sqlite_round_trip_returns_aware_utc(self):
        plus_two = timezone(timedelta(hours=2))
        value = datetime(2026, 11, 22, 12, 0, tzinfo=plus_two)
        with self.engine.begin() as conn:
            conn.execute(self.table.insert().values(id=1, at=value))
            row = conn.execute(self.table.select()).first()
        self.assertEqual(row["at"], datetime(2026, 11, 22, 10, 0, tzinfo=UTC))

    def test_legacy_naive_row_is_read_as_utc(self):
        with self.engine.begin() as conn:
            conn.execute(
                self.table.insert().values(
                    id=1, at=datetime(2026, 11, 22, 10, 0)))
            row = conn.execute(self.table.select()).first()
        self.assertEqual(row["at"], datetime(2026, 11, 22, 10, 0, tzinfo=UTC))

    def test_none_round_trip(self):
        with self.engine.begin() as conn:
            conn.execute(self.table.insert().values(id=1, at=None))
            row = conn.execute(self.table.select()).first()
        self.assertIsNone(row["at"])


if __name__ == "__main__":
    unittest.main()
