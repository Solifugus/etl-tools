"""Offline tests: no test performs network access.

The network behaviours these modules exist to handle -- FRED's and Treasury's
opposite User-Agent filters -- are documented in the source and exercised by
examples/, not asserted here, because a test that needs the internet fails for
reasons that have nothing to do with the code.
"""

from __future__ import annotations

import sqlite3
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from etools.core.run import run
from etools.db import rates
from etools.lineage.store import LineageStore
from etools.sources._obs import Observation
from etools.sources.treasury import FIELDS, UnknownSeries, yields

NS = "test://source"


def obs(series, day, value):
    return Observation(series, date(2026, 9, day), Decimal(value), NS)


class UpsertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.db = rates.connect_sqlite(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_insert_then_idempotent(self):
        rows = [obs("DGS5", 17, "4.78"), obs("DGS10", 17, "4.94")]
        first = rates.upsert_observations(self.db, rows)
        self.assertEqual((first.inserted, first.revised, first.unchanged), (2, 0, 0))

        second = rates.upsert_observations(self.db, rows)
        self.assertEqual((second.inserted, second.revised, second.unchanged), (0, 0, 2))

        n = self.db.conn.execute("select count(*) from rates_daily").fetchone()[0]
        self.assertEqual(n, 2, "a re-run must not duplicate rows")

    def test_revision_is_reported_not_hidden(self):
        rates.upsert_observations(self.db, [obs("DGS10", 17, "9.99")])
        report = rates.upsert_observations(self.db, [obs("DGS10", 17, "4.94")])

        self.assertEqual((report.inserted, report.revised, report.unchanged), (0, 1, 0))
        series, day, old, new = report.revisions[0]
        self.assertEqual((series, old, new),
                         ("DGS10", Decimal("9.99"), Decimal("4.94")))

        stored = self.db.conn.execute(
            "select value from rates_daily where series='DGS10'").fetchone()[0]
        self.assertEqual(Decimal(stored), Decimal("4.94"))

    def test_empty_load_is_not_an_error(self):
        report = rates.upsert_observations(self.db, [])
        self.assertEqual(report.total, 0)


class LineageTests(unittest.TestCase):
    def test_run_records_both_ends_without_caller_bookkeeping(self):
        with TemporaryDirectory() as tmp:
            lineage_db = Path(tmp) / "lineage.db"
            db = rates.connect_sqlite(Path(tmp) / "t.db")

            with run("unit-test", db=lineage_db):
                rates.upsert_observations(db, [obs("DGS5", 17, "4.78")])

            store = LineageStore(lineage_db)
            runs = store.runs()
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["status"], "completed")

            detail = store.run_detail(runs[0]["run_id"])
            directions = {d["direction"] for d in detail}
            self.assertIn("output", directions)
            self.assertEqual(detail[0]["rows"], 1)

    def test_failed_run_is_left_unfinished_not_completed(self):
        with TemporaryDirectory() as tmp:
            lineage_db = Path(tmp) / "lineage.db"
            with self.assertRaises(ValueError):
                with run("doomed", db=lineage_db):
                    raise ValueError("boom")

            runs = LineageStore(lineage_db).runs()
            self.assertEqual(runs[0]["status"], "failed")


class TreasuryTests(unittest.TestCase):
    def test_unknown_series_names_what_is_known(self):
        with self.assertRaises(UnknownSeries) as cm:
            yields(["DGS5", "DGS99"])
        self.assertIn("DGS99", str(cm.exception))

    def test_the_two_series_we_care_about_are_mapped(self):
        self.assertEqual(FIELDS["DGS5"], "BC_5YEAR")
        self.assertEqual(FIELDS["DGS10"], "BC_10YEAR")


if __name__ == "__main__":
    unittest.main()
