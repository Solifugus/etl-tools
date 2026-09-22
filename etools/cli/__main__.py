# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""``python -m etools <verb>`` -- thin wrappers, no logic of their own."""

from __future__ import annotations

import argparse
import sys

from ..core.http import FetchError
from ..db import rates
from ..lineage.store import DEFAULT_DB, LineageStore
from ..pipelines import daily_rates


def _open(args) -> rates.DB:
    if args.postgres:
        return rates.connect_postgres(args.postgres)
    return rates.connect_sqlite(args.sqlite)


def cmd_rates(args) -> int:
    db = _open(args)
    obs, origin, report = daily_rates.load(
        db, series=tuple(args.series), year=args.year,
        cache_ttl=None if args.no_cache else 3600)
    print(f"source     : {origin}")
    print(f"observations: {len(obs)}")
    print(f"inserted={report.inserted} revised={report.revised} "
          f"unchanged={report.unchanged}")
    for s, d, old, new in report.revisions:
        print(f"  REVISED {s} {d}: {old} -> {new}")
    if args.cross_check:
        diffs = daily_rates.cross_check(obs, tuple(args.series))
        print(f"cross-check : {len(diffs)} disagreement(s) with FRED")
        for s, d, mine, theirs in diffs[:10]:
            print(f"  {s} {d}: stored {mine}, FRED {theirs}")
    return 0


def cmd_lineage(args) -> int:
    store = LineageStore(args.lineage_db)
    for r in store.runs(args.limit):
        print(f"{r['started']}  {r['status']:<9} {r['job']}  {r['run_id'][:8]}")
        for d in store.run_detail(r["run_id"]):
            arrow = "->" if d["direction"] == "output" else "<-"
            print(f"    {arrow} {d['namespace']}/{d['name']}  rows={d['rows']}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="etools")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("rates", help="fetch and upsert daily Treasury yields")
    r.add_argument("--series", nargs="+", default=list(daily_rates.SERIES))
    r.add_argument("--year", type=int)
    r.add_argument("--sqlite", default="rates.db")
    r.add_argument("--postgres", help="DSN, e.g. postgresql:///rates")
    r.add_argument("--cross-check", action="store_true")
    r.add_argument("--no-cache", action="store_true")
    r.set_defaults(fn=cmd_rates)

    l = sub.add_parser("lineage", help="show recorded runs")
    l.add_argument("--limit", type=int, default=10)
    l.add_argument("--lineage-db", default=str(DEFAULT_DB))
    l.set_defaults(fn=cmd_lineage)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except (FetchError, OSError) as e:
        # Expected failures -- unreachable source, unreachable database. Under
        # a timer these are what systemd needs to see as a non-zero exit, and
        # a traceback would only bury the one line that matters in the journal.
        print(f"etools: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
