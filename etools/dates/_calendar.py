# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Business calendars: data, not configuration.

A calendar is an ordinary value the caller builds and passes explicitly to
every verb, so two teams can hold different calendars in one program and
holidays can come from a file or a database (``datetime_design.md`` §5).

**No holiday packs ship here, and that is deliberate** -- the same call
gBASIC made on 2026-08-20. Observed-versus-actual rules differ per employer
inside one country (which is why ``observe`` exists at all); packs rot
silently, and a holiday moved by decree becomes a wrong ``is_business_day``
with no error anywhere. A wrong holiday from your data is your data bug; a
wrong holiday from a pack we shipped would be ours, forever.

What Python *does* have is workalendar, which is a genuinely strong contender
for the data. It is adopted rather than reimplemented, behind an extra, in
``etools.dates.holidays`` -- as an explicit conversion at a named boundary,
not as a default that decides your holidays for you.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from ._core import DAY_NAMES, as_day

__all__ = [
    "Calendar", "Hours", "DEFAULT", "add_business_days",
    "business_days_between", "calendar", "is_business_day", "merge",
    "next_business_day", "previous_business_day",
]

_WEEKDAY_NAMES = frozenset(n.lower() for n in DAY_NAMES)


@dataclass(frozen=True, slots=True)
class Hours:
    """A working window.

    The fields are ``open``/``close`` rather than ``start``/``end`` because
    gBASIC's are: ``end`` is a keyword there that can be a record key but
    cannot follow a dot, so ``cal.hours.end`` is a parse error. Python would
    permit ``end``, and the names still stay -- the translation law changes
    the spelling of the *mechanism*, never the names, or a spec file stops
    being readable by both trees.
    """

    open: str
    close: str

    @property
    def minutes(self) -> tuple[int, int]:
        return (_time_minutes(self.open), _time_minutes(self.close))


def _time_minutes(t: str) -> int:
    h, m = str(t).split(":")[:2]
    return int(h) * 60 + int(m)


@dataclass(frozen=True, slots=True)
class Calendar:
    """Weekend shape, holidays, and optionally a working window.

    Built by :func:`calendar`; constructing one directly is fine but skips
    the normalisation the constructor does once (lowercasing, day-precision
    holidays, observed days).
    """

    weekend: tuple[str, ...] = ("saturday", "sunday")
    holidays: tuple[date, ...] = ()
    hours: Hours | None = None
    # Membership is asked once per day walked, and the walks are long --
    # business_days_between over a decade asks it 3,650 times. compare=False
    # so it never contributes to equality; it is derived, not stated.
    _index: frozenset = field(default=frozenset(), compare=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_index", frozenset(self.holidays))


def calendar(*, weekend=("saturday", "sunday"), holidays=(), observe=None,
             hours=None) -> Calendar:
    """Build a calendar. ``calendar()`` is Sat/Sun with no holidays.

    gBASIC takes one record because its functions have fixed arity, so the
    defaults live in the constructor. Python takes keyword-only arguments:
    the same guarantee, enforced by the language. ``calendar(**spec)`` reads
    a spec loaded from a file, which is the case the record form existed for.

    One behaviour differs, and in Python's favour. gBASIC's ``dates.calendar``
    reads its record with ``has(spec, ...)``, so a misspelled ``holidayz:``
    is silently ignored and you get a calendar with no holidays and no
    complaint -- while eleven other gBASIC stdlib libraries refuse unknown
    options through ``_options()``, naming the known set. Keyword-only
    arguments refuse it here by construction. Recorded as an upstream defect;
    the fix belongs in ``dates.bas`` (``porting-plan.md`` §1.2).
    """
    weekend = tuple(str(w).strip().lower() for w in weekend)
    for w in weekend:
        if w not in _WEEKDAY_NAMES:
            raise ValueError(
                f"dates: unknown weekday '{w}' (known: "
                + ", ".join(sorted(_WEEKDAY_NAMES)) + ")")

    # Normalised to day precision here, once, so membership tests never hit
    # the precision rule: a holiday supplied as a full timestamp still blocks
    # the whole day.
    days = [as_day(h) for h in holidays]

    if observe is not None:
        days = _observed(days, weekend, observe)

    if hours is not None and not isinstance(hours, Hours):
        if set(hours) != {"open", "close"}:
            raise ValueError(
                "dates: hours must be { open:, close: } (got: "
                + ", ".join(sorted(map(str, hours))) + ")")
        hours = Hours(open=hours["open"], close=hours["close"])

    return Calendar(weekend=weekend,
                    holidays=tuple(sorted(set(days))),
                    hours=hours)


def _observed(days, weekend, observe):
    """Add the observed day when a holiday lands on the weekend.

    ``"nearest"`` picks the closest free weekday, ties breaking forward -- the
    US federal rule, which generalises to any weekend shape. ``"forward"``
    always shifts to the next free weekday, the UK substitute-day style.
    Chains resolve: two weekend holidays observing forward take consecutive
    weekdays rather than colliding.

    The original day stays in the list -- it is already non-working via the
    weekend -- and the observed day is ADDED, computed once here, so every
    downstream verb inherits it with no further logic.
    """
    if observe not in ("nearest", "forward"):
        raise ValueError("dates: observe must be nearest or forward")
    observed = list(days)
    for h in days:
        if DAY_NAMES[h.weekday()].lower() not in weekend:
            continue
        for dist in range(1, 31):
            fwd = h + timedelta(days=dist)
            if DAY_NAMES[fwd.weekday()].lower() not in weekend and fwd not in observed:
                observed.append(fwd)
                break
            if observe == "nearest":
                back = h - timedelta(days=dist)
                if DAY_NAMES[back.weekday()].lower() not in weekend and back not in observed:
                    observed.append(back)
                    break
    return observed


#: Sat/Sun, no holidays. What every verb uses when ``cal`` is omitted.
DEFAULT = calendar()


def _cal(cal) -> Calendar:
    return DEFAULT if cal is None else cal


def is_business_day(d, cal=None) -> bool:
    """Not a weekend day under this calendar, and not a holiday."""
    cal = _cal(cal)
    dd = as_day(d)
    if DAY_NAMES[dd.weekday()].lower() in cal.weekend:
        return False
    return dd not in cal._index


def _step_business(d, cal, direction):
    dd = as_day(d)
    for _ in range(3700):          # ~10 years of days
        dd = dd + timedelta(days=direction)
        if is_business_day(dd, cal):
            return dd
    # Without this, a calendar with no business days at all -- which merge can
    # legitimately produce -- turns a lookup into a hang, the least debuggable
    # outcome there is.
    raise ValueError("dates: no business day within 10 years; is the calendar empty?")


def next_business_day(d, cal=None):
    """The first business day STRICTLY after d."""
    return _step_business(d, _cal(cal), 1)


def previous_business_day(d, cal=None):
    """The last business day strictly before d."""
    return _step_business(d, _cal(cal), -1)


def add_business_days(d, n, cal=None):
    """Move n business days from d. n may be negative; 0 does not move."""
    cal = _cal(cal)
    dd = as_day(d)
    for _ in range(abs(n)):
        dd = _step_business(dd, cal, 1 if n > 0 else -1)
    return dd


def business_days_between(a, b, cal=None) -> int:
    """Business days d with a < d <= b. Signed: b before a negates.

    The half-open convention is stated rather than left to be discovered,
    because half-open intervals are where calendar bugs live. Read it as "how
    many working days until the deadline" when a is today.
    """
    cal = _cal(cal)
    aa, bb = as_day(a), as_day(b)
    if bb < aa:
        return -business_days_between(b, a, cal)
    total = 0
    dd = aa
    while dd < bb:
        dd += timedelta(days=1)
        if is_business_day(dd, cal):
            total += 1
    return total


def merge(cals) -> Calendar:
    """Combine calendars as a UNION OF CONSTRAINTS.

    This is why finding mutual meeting days needs no new search machinery:
    merge, then use any verb already here. The law that makes it testable by
    arithmetic::

        is_business_day(d, merge([a, b]))
            == is_business_day(d, a) and is_business_day(d, b)

    Hours intersect -- latest open, earliest close -- and a merge may
    legitimately produce an empty window (one calendar closes before the
    other opens). Consumers handle that; merge never raises.
    """
    weekend: list[str] = []
    holidays: list[date] = []
    open_txt = close_txt = None
    for c in cals:
        for w in c.weekend:
            if w not in weekend:
                weekend.append(w)
        for h in c.holidays:
            if h not in holidays:
                holidays.append(h)
        if c.hours is not None:
            if open_txt is None:
                open_txt, close_txt = c.hours.open, c.hours.close
            else:
                if _time_minutes(c.hours.open) > _time_minutes(open_txt):
                    open_txt = c.hours.open
                if _time_minutes(c.hours.close) < _time_minutes(close_txt):
                    close_txt = c.hours.close
    return Calendar(weekend=tuple(weekend),
                    holidays=tuple(sorted(holidays)),
                    hours=None if open_txt is None else Hours(open_txt, close_txt))
