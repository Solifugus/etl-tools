# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""One spec vocabulary, three verbs (``datetime_design.md`` §7).

"Third Thursday", "first Tuesday after the 15th", "last Wednesday of the
month", "first business day before the deadline" are one question family --
*which day satisfies these constraints, relative to this anchor?* -- and they
get one vocabulary::

    matches(d, spec, cal)        # boolean: does d satisfy spec?
    select(spec, anchor, cal)    # the ONE day, or UNKNOWN
    series(spec, bounds, cal)    # ALL of them

**A spec is a dict, and stays a dict.** Not keyword arguments, not a fluent
chain, not a string mini-language. The target systems -- physician rosters,
recurring meetings, company calendars -- keep their recurrence rules in a
database or a config file, build them from a UI, and inspect them when
something goes wrong. A dict does all of that natively; a chain exists only in
source, written in advance. iCalendar's RRULE is the cautionary tale for the
string form: a vocabulary that grew until nobody could write it unaided.

It also means ``except:`` needs no trailing underscore. The three sanctioned
deviations from the translation law include renaming Python keywords, and
keeping specs as data avoids spending that deviation at all.

**A malformed spec raises; a spec no day satisfies yields UNKNOWN.** The two
failure modes mean different things and must not be collapsed -- the fifth
Tuesday of a four-Tuesday month is a legitimate answer of "there isn't one",
and scheduling code probes for exactly that.
"""

from __future__ import annotations

from datetime import date, timedelta

from tervalue import UNKNOWN

from ._calendar import (DEFAULT, is_business_day, next_business_day,
                        previous_business_day)
from ._core import DAY_NAMES, add_months, as_day, at

__all__ = ["matches", "select", "series"]

SPEC_FIELDS = frozenset({
    "weekday", "nth", "day", "month", "kind", "within", "after",
    "on_or_after", "before", "on_or_before", "at", "every", "when",
    "except", "roll",
})
BOUNDS_FIELDS = frozenset({"from", "through", "count"})


def _check(spec, known, what):
    """Refuse an unknown field, naming the known set.

    gBASIC's ``dates.bas`` reads its specs with ``has(spec, ...)`` and so
    ignores a misspelling silently -- ``{nth: 3, weekdy: "thursday"}`` quietly
    becomes "the third day of the month". Eleven other gBASIC stdlib
    libraries refuse unknown options through ``_options()``, naming the known
    set; this one does not, and that is the inconsistency rather than the
    intent. Axiom 6 says never silently guess. Recorded as an upstream defect.
    """
    unknown = [str(k) for k in spec if k not in known]
    if unknown:
        raise ValueError(
            f"dates: unknown {what} '{unknown[0]}' (known: "
            + ", ".join(sorted(known)) + ")")


def _cal(cal):
    return DEFAULT if cal is None else cal


def _mkday(y, m, d) -> date:
    return date(y, m, d)


def _scope(d, within):
    """The first and last day of the scope ``within`` around d.

    Leans on clamped month arithmetic rather than a day table: the last day of
    a month is first-of-month plus one month minus one day, which is correct
    in February because the add clamps.
    """
    dd = as_day(d)
    if within == "month":
        first = _mkday(dd.year, dd.month, 1)
        return first, add_months(first, 1) - timedelta(days=1)
    if within == "quarter":
        first = _mkday(dd.year, (dd.month - 1) // 3 * 3 + 1, 1)
        return first, add_months(first, 3) - timedelta(days=1)
    if within == "year":
        return _mkday(dd.year, 1, 1), _mkday(dd.year, 12, 31)
    if within == "week":
        first = dd - timedelta(days=dd.weekday())    # ISO week: Monday first
        return first, first + timedelta(days=6)
    raise ValueError("dates: within must be week, month, quarter, or year")


def _nth_num(v) -> int:
    """``"last"`` is -1. Any other string is a refusal, not a guess.

    gBASIC returns -1 for *any* string here, so ``nth: "first"`` silently
    means last -- the documented vocabulary is the number or ``"last"``, and
    nothing else. Second upstream defect found by this port.
    """
    if isinstance(v, str):
        if v.strip().lower() == "last":
            return -1
        raise ValueError(f'dates: nth must be a number or "last" (got \'{v}\')')
    return int(v)


def _wd_ok(d, w) -> bool:
    name = DAY_NAMES[d.weekday()].lower()
    if isinstance(w, (list, tuple, set, frozenset)):
        return any(str(x).strip().lower() == name for x in w)
    return str(w).strip().lower() == name


def _excepted(dd, spec) -> bool:
    return any(as_day(e) == dd for e in spec.get("except", ()))


def _candidate(dd, spec, cal) -> bool:
    """The non-positional constraints: is this day even eligible?"""
    if "weekday" in spec and not _wd_ok(dd, spec["weekday"]):
        return False
    if "day" in spec and dd.day != spec["day"]:
        return False
    if "month" in spec:
        # A number, or a list: {day: 15, month: [1, 7]} is "the 15th of
        # January and July" -- RRULE's BYMONTH.
        want = spec["month"]
        if isinstance(want, (list, tuple, set, frozenset)):
            if dd.month not in want:
                return False
        elif dd.month != want:
            return False
    if spec.get("kind") == "business" and not is_business_day(dd, cal):
        return False
    return not _excepted(dd, spec)


def _bound(b, ref) -> date:
    """An anchor bound: a day, or ``{"day": 15}`` meaning day 15 of ref's month."""
    if isinstance(b, dict):
        return _mkday(ref.year, ref.month, b["day"])
    return as_day(b)


def _apply_roll(dd, spec, cal):
    if "roll" not in spec or is_business_day(dd, cal):
        return dd
    roll = spec["roll"]
    if roll == "forward":
        return next_business_day(dd, cal)
    if roll == "backward":
        return previous_business_day(dd, cal)
    if roll == "modified":
        # Forward, unless that crosses into the next month -- then back. The
        # finance convention, where a payment date must stay in its
        # accounting month.
        f = next_business_day(dd, cal)
        return previous_business_day(dd, cal) if f.month != dd.month else f
    raise ValueError("dates: roll must be forward, backward, or modified")


def _finish(dd, spec, cal):
    rolled = _apply_roll(dd, spec, cal)
    return at(rolled, spec["at"]) if "at" in spec else rolled


def matches(d, spec, cal=None) -> bool:
    """Does d satisfy spec?"""
    _check(spec, SPEC_FIELDS, "spec field")
    cal = _cal(cal)
    dd = as_day(d)
    if not _candidate(dd, spec, cal):
        return False
    if "after" in spec and not dd > _bound(spec["after"], dd):
        return False
    if "on_or_after" in spec and not dd >= _bound(spec["on_or_after"], dd):
        return False
    if "before" in spec and not dd < _bound(spec["before"], dd):
        return False
    if "on_or_before" in spec and not dd <= _bound(spec["on_or_before"], dd):
        return False
    if "nth" in spec:
        first, last = _scope(dd, spec.get("within", "month"))
        total = mypos = 0
        cur = first
        while cur <= last:
            if _candidate(cur, spec, cal):
                total += 1
                if cur == dd:
                    mypos = total
            cur += timedelta(days=1)
        n = _nth_num(spec["nth"])
        return mypos == (n if n > 0 else total + 1 + n)
    return True


def select(spec, anchor, cal=None):
    """The one day satisfying spec, relative to anchor -- or ``UNKNOWN``.

    ``UNKNOWN`` rather than an exception when nothing satisfies the spec (a
    fifth Tuesday; a business day before Monday in a holiday week), because
    scheduling code probes, and a miss is absent information rather than a
    mistake.
    """
    _check(spec, SPEC_FIELDS, "spec field")
    cal = _cal(cal)
    aa = as_day(anchor)
    n = _nth_num(spec["nth"]) if "nth" in spec else 1

    direction, bound, inclusive = 0, aa, False
    for key, d, inc in (("after", 1, False), ("on_or_after", 1, True),
                        ("before", -1, False), ("on_or_before", -1, True)):
        if key in spec:
            direction, bound, inclusive = d, _bound(spec[key], aa), inc
    if direction == 0 and "nth" not in spec and "within" not in spec:
        # Bare spec: the "next X" reading -- first candidate STRICTLY after
        # the anchor, matching next_weekday's exclusive convention.
        direction = 1

    if direction != 0:
        if n < 1:
            raise ValueError(
                "dates.select: nth must be positive when searching from an anchor")
        dd = bound if inclusive else bound + timedelta(days=direction)
        seen = 0
        for _ in range(3701):
            if _candidate(dd, spec, cal):
                seen += 1
                if seen == n:
                    return _finish(dd, spec, cal)
            dd += timedelta(days=direction)
        return UNKNOWN                      # a miss, not an error

    if "nth" not in spec:
        raise ValueError(
            "dates.select: nth is required with within (or use after/before)")
    first, last = _scope(aa, spec.get("within", "month"))
    found = []
    cur = first
    while cur <= last:
        if _candidate(cur, spec, cal):
            found.append(cur)
        cur += timedelta(days=1)
    idx = n if n > 0 else len(found) + 1 + n
    if idx < 1 or idx > len(found):
        return UNKNOWN                      # e.g. the fifth Tuesday
    return _finish(found[idx - 1], spec, cal)


def _advance(first, unit, k):
    if unit == "week":
        return first + timedelta(days=7 * k)
    if unit == "month":
        return add_months(first, k)
    if unit == "quarter":
        return add_months(first, 3 * k)
    return add_months(first, 12 * k)


def _step_to(start, every, k, prev, cal):
    if isinstance(every, timedelta):
        return start + every * k
    if every == "day":
        return start + timedelta(days=k)
    if every == "week":
        return start + timedelta(days=7 * k)
    if every == "month":
        return add_months(start, k)
    if every == "quarter":
        return add_months(start, 3 * k)
    if every == "year":
        return add_months(start, 12 * k)
    if every == "business day":
        return next_business_day(prev, cal)
    raise ValueError("dates.series: every must be a duration or one of "
                     "day, week, month, quarter, year, business day")


def _candidates_in(sub, anchor, cal):
    """Every candidate day in sub's scope around anchor, in order.

    This is what ``when:`` WITHOUT ``nth:`` means: not "the nth such day each
    period" but EVERY such day -- Mon/Wed/Fri standups, all business days of
    the month, the 1st and the 15th. RRULE's BYDAY with no BYSETPOS.
    """
    first, last = _scope(anchor, sub["within"])
    out = []
    cur = first
    while cur <= last:
        if _candidate(cur, sub, cal):
            out.append(cur)
        cur += timedelta(days=1)
    return out


def series(spec, bounds, cal=None) -> list:
    """Every day satisfying spec within bounds.

    ``bounds`` is ``{"from": d, "through": d}`` (inclusive) or
    ``{"from": d, "count": n}``. The names are gBASIC's, where ``to:`` is a
    parse error and ``through`` is honest about being inclusive.
    """
    _check(spec, SPEC_FIELDS, "spec field")
    _check(bounds, BOUNDS_FIELDS, "bounds field")
    cal = _cal(cal)
    start = as_day(bounds["from"])
    want = bounds.get("count", -1)
    has_through = "through" in bounds
    stop_at = as_day(bounds["through"]) if has_through else start
    if not has_through and want < 1:
        raise ValueError("dates.series: bounds need through: or count:")

    out: list = []
    if "when" in spec:
        # Period mode: every period, the day (or days) the sub-rule picks.
        unit = spec.get("every", "")
        if unit not in ("week", "month", "quarter", "year"):
            raise ValueError(
                "dates.series: when: needs every: week, month, quarter, or year")
        # A COPY. gBASIC writes sub.within into the caller's record; here that
        # would mutate the dict the caller may reuse next loop iteration.
        sub = {**spec["when"], "within": unit}
        _check(sub, SPEC_FIELDS, "spec field")
        first, _ = _scope(start, unit)
        for k in range(10000):
            anchor = _advance(first, unit, k)
            if has_through and anchor > stop_at:
                return out
            if "nth" in sub:
                picked = [select(sub, anchor, cal)]
            else:
                picked = _candidates_in(sub, anchor, cal)
            for d in picked:
                if d is UNKNOWN:
                    continue
                dd = as_day(d)
                if dd < start:
                    continue
                if has_through and dd > stop_at:
                    return out
                if _excepted(dd, spec):
                    continue            # a gap, not a reschedule
                out.append(_finish(dd, spec, cal))
                if want > 0 and len(out) >= want:
                    return out
        return out

    # Stepping mode. Steps are MULTIPLICATIVE from the start -- start + step*k,
    # never cumulative -- so monthly from Jan 31 gives Feb 28 then MAR 31, not
    # the Feb-28-forever drift that cumulative clamping causes.
    if "every" not in spec:
        raise ValueError("dates.series: spec needs every: (or when: with every:)")
    every = spec["every"]
    if isinstance(every, timedelta) and every == timedelta(0):
        raise ValueError("dates.series: every cannot be zero")

    dd = start
    if every == "business day" and not is_business_day(dd, cal):
        dd = next_business_day(dd, cal)
    for k in range(10000):
        if has_through and dd > stop_at:
            return out
        if not _excepted(dd, spec):
            out.append(_finish(dd, spec, cal))
            if want > 0 and len(out) >= want:
                return out
        dd = _step_to(start, every, k + 1, dd, cal)
    return out
