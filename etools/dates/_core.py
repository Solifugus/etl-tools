# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Day arithmetic: the parts that need no calendar.

Ported from gBASIC ``stdlib/dates.bas`` under the translation law
(``docs/porting-plan.md`` §1.1): same function names, same argument order,
same error text.

**The one structural decision.** gBASIC has a single datetime kind that
carries its own precision, so ``2026-03-15`` and ``2026-03-15 09:30`` are the
same kind at two precisions. Python has ``date`` and ``datetime``, and that
split maps onto the only precision boundary this library actually uses: day
versus finer. So ``date`` *is* the day-precision value, and every function
that gBASIC opens with ``dd {day}= d`` opens here with ``as_day(d)``.

That is an ADOPT, not a port: rebuilding the precision-carrying kind would
mean rebuilding ``datetime``, and the roadmap's selection rule says a strong
contender is adopted rather than reimplemented. What gets built is the part
Python has no answer for -- calendars as data, and the selector vocabulary.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta

__all__ = [
    "DAY_NAMES", "as_day", "at", "add_months", "between", "dayname",
    "days_between", "end_of_month", "next_weekday", "previous_weekday",
    "start_of_month",
]

# Monday first, matching d.weekday() and gBASIC's ISO d.weekday (1..7).
# Hardcoded rather than taken from the locale: a calendar spec written
# ``weekday: "thursday"`` must mean Thursday on a machine set to fr_FR.
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday")


def as_day(d) -> date:
    """Truncate to day precision -- gBASIC's ``dd {day}= d``.

    A ``datetime`` loses its time, a ``date`` is already there, and an ISO
    string is parsed. The truncation is done once, at the boundary of every
    public function, so membership tests never compare a stamp against a day
    and quietly miss (``datetime_design.md`` §5).
    """
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return _parse(d).date() if _has_time(d) else date.fromisoformat(d)
    raise TypeError(f"dates: expected a date, datetime, or ISO string, got {type(d).__name__}")


def as_moment(d) -> datetime:
    """Widen to a datetime, midnight if it is a day. For the hours verbs."""
    if isinstance(d, datetime):
        return d
    if isinstance(d, date):
        return datetime(d.year, d.month, d.day)
    if isinstance(d, str):
        return _parse(d)
    raise TypeError(f"dates: expected a date, datetime, or ISO string, got {type(d).__name__}")


def _has_time(s: str) -> bool:
    return " " in s or "T" in s


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace(" ", "T"))


def add_months(d, k: int):
    """Add k months by the accountant's rule: month first, then CLAMP the day.

    ``Jan 31 + 1 month`` is Feb 28, not Mar 3 (``datetime_design.md`` §4.1).
    The order is normative -- Java, dateutil and JS Temporal converged on it
    independently -- and it is why ``series`` steps ``start + step*k`` rather
    than accumulating: monthly from Jan 31 gives Feb 28 then MAR 31, where
    cumulative clamping would give Feb 28 forever.
    """
    total = (d.year * 12 + d.month - 1) + k
    year, month = divmod(total, 12)
    month += 1
    return d.replace(year=year, month=month,
                     day=min(d.day, monthrange(year, month)[1]))


def dayname(d) -> str:
    """The weekday name, "Monday".."Sunday"."""
    return DAY_NAMES[as_day(d).weekday()]


def days_between(a, b) -> int:
    """Signed whole days from a to b. b before a is negative."""
    return (as_day(b) - as_day(a)).days


def between(a, b, unit):
    """Calendar difference in days, months, or years. Signed.

    "How many months apart" is a calendar question, deliberately not answered
    by ``b - a``, which yields an exact duration and can never yield months.
    Consistent with the accountant's rule by construction: the month count k
    is the largest k with ``a + k months`` (clamped) still on or before b, so
    Jan 31 -> Feb 28 is 1 month exactly as Jan 31 + 1 month is Feb 28.
    """
    aa, bb = as_day(a), as_day(b)
    if unit == "days":
        return (bb - aa).days
    if unit in ("months", "years"):
        if bb < aa:
            return -between(b, a, unit)
        k = (bb.year * 12 + bb.month) - (aa.year * 12 + aa.month)
        if add_months(aa, k) > bb:
            k -= 1
        return k // 12 if unit == "years" else k
    raise ValueError("dates.between: unit must be days, months, or years")


def time_of_day(t) -> timedelta:
    """A time of day as an exact duration since midnight.

    gBASIC adds no ``time`` kind because one is not needed: 09:30 *is*
    9 hours 30 minutes since midnight, arithmetically and honestly
    (``datetime_design.md`` §6). In specs and calendars times stay strings,
    exactly as weekdays do, so the records remain serialisable data.
    """
    if isinstance(t, timedelta):
        return t
    parts = str(t).split(":")
    secs = int(parts[0]) * 3600 + int(parts[1]) * 60
    if len(parts) > 2:
        secs += int(parts[2])
    return timedelta(seconds=secs)


def at(d, t):
    """A day plus a time of day. t is a string ("14:00") or a timedelta.

    Returns a ``datetime`` -- except at midnight, which returns the ``date``
    unchanged. That is not a special case bolted on: in gBASIC adding a zero
    duration does not bump precision, so a midnight stamp keeps day precision
    and renders without a time. ``date`` is how Python spells that.
    """
    dd = as_day(d)
    delta = time_of_day(t)
    if delta == timedelta(0):
        return dd
    return datetime(dd.year, dd.month, dd.day) + delta


def end_of_month(d):
    """Last day of d's month. gBASIC's ``{end of month}=`` modifier."""
    dd = as_day(d)
    return dd.replace(day=monthrange(dd.year, dd.month)[1])


def start_of_month(d):
    """First day of d's month. gBASIC's ``{start of month}=`` modifier."""
    return as_day(d).replace(day=1)


def _weekday_index(name: str) -> int:
    want = str(name).strip().lower()
    for i, n in enumerate(DAY_NAMES):
        if n.lower() == want:
            return i
    raise ValueError(
        f"dates: unknown weekday '{name}' (known: "
        + ", ".join(n.lower() for n in DAY_NAMES) + ")")


def next_weekday(d, name):
    """The next named weekday, STRICTLY after d.

    gBASIC's ``{next friday}=`` family, which is fourteen modifiers there and
    two functions here because Python has no modifiers. Strictness is the
    point: from a Friday, ``next_weekday(d, "friday")`` is seven days on, not
    today -- the trap the ``after:``/``on_or_after:`` spec names exist to
    avoid reproducing.
    """
    target = _weekday_index(name)
    dd = as_day(d) + timedelta(days=1)
    return dd + timedelta(days=(target - dd.weekday()) % 7)


def previous_weekday(d, name):
    """The previous named weekday, strictly before d."""
    target = _weekday_index(name)
    dd = as_day(d) - timedelta(days=1)
    return dd - timedelta(days=(dd.weekday() - target) % 7)
