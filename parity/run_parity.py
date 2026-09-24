#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Run the shared parity cases against the Python tree.

Its twin, ``run_parity.bas``, runs the *same files* against gBASIC. A case that
disagrees fails in whichever tree is wrong, and the case file is the arbiter --
neither implementation gets to be right merely by being the one that was asked.

**The format is tab-separated, deliberately.** JSON was the first instinct and
was wrong: gBASIC's ``crypto.json_decode`` is documented as flat, so a nested
case file would have been readable by one side only, and a harness whose two
halves disagree about how to *read* the questions cannot arbitrate the answers.
Six tab-separated columns are unambiguous in both.

    expr <TAB> ccy <TAB> amount <TAB> operand <TAB> expect <TAB> name

``operand`` is ``-`` when unused. An ``expect`` starting with ``!`` is an
error and the rest is its message, verbatim -- error text is part of the public
surface (``porting-plan.md`` §1.1).

A ``name`` starting with ``gbasic-defect:`` marks a case this tree passes and
gBASIC is known to fail. It is a full failure here and a reported-but-tolerated
divergence there, which is the right asymmetry when the defect is upstream.

Case files name their calendars and specs rather than spelling them out,
and both runners build the named thing identically. A case that disagrees is
then a disagreement about *behaviour*, never about which calendar was meant.

Usage:  python parity/run_parity.py [cases/money.tsv ...]
"""

from __future__ import annotations

import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "packages" / "tervalue"))
sys.path.insert(0, str(ROOT.parent))

from tervalue import UNKNOWN, Money  # noqa: E402

from etools import dates as D  # noqa: E402


def _num(text: str):
    """An operand is an int when it looks like one, else a Decimal."""
    return int(text) if text.lstrip("-").isdigit() else Decimal(text)


MONEY = {
    "show":   lambda c, a, _: str(Money.of(c, a).posted),
    "text":   lambda c, a, _: Money.of(c, a).text(),
    "text2":  lambda c, a, _: Money.of(c, a).text(2),
    "mul":    lambda c, a, n: str((Money.of(c, a) * _num(n)).posted),
    "div":    lambda c, a, n: str((Money.of(c, a) / _num(n)).posted),
    "divmul": lambda c, a, n: str((Money.of(c, a) / _num(n) * _num(n)).posted),
    "accum":  lambda c, a, n: str(sum((Money.of(c, a) for _ in range(int(n))),
                                      Money.zero(c)).posted),
}

# ---------------------------------------------------------------- dates

_ALL_DAYS = [n.lower() for n in D.DAY_NAMES]

CALENDARS = {
    "plain":      lambda: D.calendar(),
    "xmas":       lambda: D.calendar(holidays=["2026-12-25"]),
    "feb13":      lambda: D.calendar(holidays=["2026-02-13"]),
    "hours":      lambda: D.calendar(hours={"open": "9:00", "close": "17:00"}),
    "xmashours":  lambda: D.calendar(holidays=["2026-12-25"],
                                     hours={"open": "9:00", "close": "17:00"}),
    "july4":      lambda: D.calendar(holidays=["2026-07-04"], observe="nearest"),
    "july4f":     lambda: D.calendar(holidays=["2026-07-04"], observe="forward"),
    "never":      lambda: D.calendar(weekend=_ALL_DAYS),
    "badobserve": lambda: D.calendar(holidays=["2026-07-04"], observe="sideways"),
}

SPECS = {
    "thu3":       {"nth": 3, "weekday": "thursday", "within": "month"},
    "wedlast":    {"nth": "last", "weekday": "wednesday", "within": "month"},
    "wedneg1":    {"nth": -1, "weekday": "wednesday", "within": "month"},
    "tue5":       {"nth": 5, "weekday": "tuesday", "within": "month"},
    "mon1q":      {"nth": 1, "weekday": "monday", "within": "quarter"},
    "fri1y":      {"nth": 1, "weekday": "friday", "within": "year"},
    "blastwk":    {"nth": -1, "kind": "business", "within": "week"},
    "tueafter15": {"nth": 1, "weekday": "tuesday", "after": {"day": 15}},
    "bbefore28":  {"nth": 1, "kind": "business", "before": "2026-12-28"},
    "monoa":      {"nth": 1, "weekday": "monday", "on_or_after": "2026-08-17"},
    "monafter":   {"weekday": "monday", "after": "2026-08-17"},
    "barefri":    {"weekday": "friday"},
    "d31mod":     {"nth": 1, "day": 31, "within": "month", "roll": "modified"},
    "d31fwd":     {"nth": 1, "day": 31, "within": "month", "roll": "forward"},
    "business":   {"kind": "business"},
    "d15m7":      {"day": 15, "month": 7},
    "board":      {"every": "month", "when": {"nth": 3, "weekday": "thursday"},
                   "at": "14:00"},
    "boardx":     {"every": "month", "when": {"nth": 3, "weekday": "thursday"},
                   "except": ["2026-03-19"]},
    "payroll":    {"every": timedelta(weeks=2), "roll": "backward"},
    "monthly":    {"every": "month"},
    "standup":    {"every": "week",
                   "when": {"weekday": ["monday", "wednesday", "friday"]}},
    "bymonth":    {"every": "month", "when": {"day": 15, "month": [1, 7]}},
    "bdays":      {"every": "business day"},
    "badroll":    {"nth": 1, "day": 31, "within": "month", "roll": "sideways"},
    "badwithin":  {"nth": 1, "weekday": "monday", "within": "fortnight"},
    "nthneg":     {"nth": -1, "weekday": "monday", "after": "2026-08-17"},
    "nonth":      {"weekday": "monday", "within": "month"},
    "badwhen":    {"every": "day", "when": {"weekday": "monday"}},
    "noevery":    {"weekday": "monday"},
    "badevery":   {"every": "fortnight"},
    # The two upstream defects: gBASIC answers where it should refuse.
    "badfield":   {"nth": 3, "weekdy": "thursday", "within": "month"},
    "nthfirst":   {"nth": "first", "weekday": "thursday", "within": "month"},
}

BOUNDS = {
    "h1":          {"from": "2026-01-01", "through": "2026-06-30"},
    "c6from0102":  {"from": "2026-01-02", "count": 6},
    "c4from0131":  {"from": "2026-01-31", "count": 4},
    "c6from0817":  {"from": "2026-08-17", "count": 6},
    "y2026":       {"from": "2026-01-01", "through": "2026-12-31"},
    "c3from1223":  {"from": "2026-12-23", "count": 3},
    "c3from0101":  {"from": "2026-01-01", "count": 3},
    "nobound":     {"from": "2026-01-01"},
}


def _cal(name):
    return CALENDARS[name]()


def _show(v) -> str:
    """Render as gBASIC's ``string()`` does -- measured, not assumed.

    Booleans are lowercase there and UNKNOWN prints as the word. Dates and
    datetimes already agree: ``string(d)`` gives ``2026-08-20`` and
    ``2026-01-15 14:00:00``, which is exactly ``str()``.
    """
    if v is UNKNOWN:
        return "unknown"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _series(name, bounds, cal):
    return D.series(SPECS[name], BOUNDS[bounds], _cal(cal))


def _at(i):
    return lambda a, b, c: _show(_series(a, b, c)[i])


DATES = {
    "dayname":               lambda a, b, c: D.dayname(a),
    "days_between":          lambda a, b, c: _show(D.days_between(a, b)),
    "between":               lambda a, b, c: _show(D.between(a, b, c)),
    "end_of_month":          lambda a, b, c: _show(D.end_of_month(a)),
    "start_of_month":        lambda a, b, c: _show(D.start_of_month(a)),
    "next_weekday":          lambda a, b, c: _show(D.next_weekday(a, b)),
    "previous_weekday":      lambda a, b, c: _show(D.previous_weekday(a, b)),
    "at":                    lambda a, b, c: _show(D.at(a, b)),
    "is_business_day":       lambda a, b, c: _show(D.is_business_day(a, _cal(b))),
    "next_business_day":     lambda a, b, c: _show(D.next_business_day(a, _cal(b))),
    "previous_business_day": lambda a, b, c: _show(D.previous_business_day(a, _cal(b))),
    "add_business_days":     lambda a, b, c: _show(D.add_business_days(a, int(b), _cal(c))),
    "business_days_between": lambda a, b, c: _show(D.business_days_between(a, b, _cal(c))),
    "holiday_count":         lambda a, b, c: _show(len(_cal(a).holidays)),
    "select":                lambda a, b, c: _show(D.select(SPECS[a], b, _cal(c))),
    "matches":               lambda a, b, c: _show(D.matches(b, SPECS[a], _cal(c))),
    "series_count":          lambda a, b, c: _show(len(_series(a, b, c))),
    "series_0":              _at(0),
    "series_1":              _at(1),
    "series_2":              _at(2),
    "series_3":              _at(3),
    "series_4":              _at(4),
    "add_bhours":            lambda a, b, c: _show(
        D.add_business_hours(a, timedelta(minutes=int(b)), _cal(c))),
    "bhours_between":        lambda a, b, c: _show(
        int(D.business_hours_between(a, b, _cal(c)).total_seconds() // 60)),
    "is_business_time":      lambda a, b, c: _show(D.is_business_time(a, _cal(b))),
}

EVALUATORS = {"money": MONEY, "dates": DATES}


def run_file(path: Path) -> tuple[int, int, int]:
    table = EVALUATORS.get(path.stem)
    passed = failed = skipped = 0
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.startswith("#") or raw.startswith("expr\t"):
            continue
        expr, ccy, amount, operand, expect, name = raw.split("\t")
        fn = (table or {}).get(expr)
        if fn is None:
            skipped += 1
            continue
        try:
            got = fn(ccy, amount, operand)
        except Exception as e:                  # noqa: BLE001 - reported, not swallowed
            got = "!" + str(e)
        if got == expect:
            passed += 1
            # A gbasic-defect case is one Python gets right and gBASIC does
            # not. It must pass *here*; the gBASIC runner reports it as known.
        else:
            failed += 1
            print(f"  FAIL {name}\n       want {expect}\n       got  {got}")
    return passed, failed, skipped


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    files = [Path(a) for a in argv] or sorted((ROOT / "cases").glob("*.tsv"))
    tp = tf = ts = 0
    for f in files:
        p, q, s = run_file(f)
        print(f"{f.name}: {p} passed, {q} failed" + (f", {s} skipped" if s else ""))
        tp, tf, ts = tp + p, tf + q, ts + s
    print(f"\npython: {tp} passed, {tf} failed, {ts} skipped")
    return 1 if tf else 0


if __name__ == "__main__":
    sys.exit(main())
