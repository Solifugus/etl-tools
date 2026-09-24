# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Holiday data from workalendar -- adopted, not reimplemented.

The roadmap's verdict for business calendars is ADOPT+BUILD: "Holiday data is
solved. ``dates``'s recurrence spec language is not." workalendar covers
roughly two hundred jurisdictions and tracks them; reimplementing that would
be a decade of maintenance for no distinctive value.

It is an **explicit conversion at a named boundary**, never a default. Calling
this is a decision you made and can point at in a code review; a calendar that
silently acquired a country's holidays is a decision nobody made.

    from workalendar.usa import UnitedStates
    from etools.dates import holidays, next_business_day

    cal = holidays.from_workalendar(UnitedStates, range(2026, 2029))
    next_business_day("2026-07-03", cal)

``source`` may also be the **string** ``"usa.UnitedStates"`` -- module path,
dot, class name -- which is the form a jurisdiction takes when it arrives from
a config file or a database column rather than from an import. A calendar is
data here, and which country's calendar is data too.

Needs the extra::

    pip install etools-etl[calendars]
"""

from __future__ import annotations

from importlib import import_module

from ._calendar import Calendar, calendar
from ._core import DAY_NAMES

__all__ = ["from_workalendar", "labels"]


def _instance(source):
    """A workalendar calendar from a class, an instance, or a dotted string."""
    if isinstance(source, str):
        if "." not in source:
            raise ValueError(
                f"dates: workalendar source must be 'module.Class', got '{source}'")
        module, _, name = source.rpartition(".")
        try:
            mod = import_module(f"workalendar.{module}")
        except ImportError as e:  # pragma: no cover - depends on install
            if e.name == "workalendar":
                raise ImportError(
                    "Holiday data needs workalendar: "
                    "pip install etools-etl[calendars]") from e
            raise ValueError(
                f"dates: no workalendar region '{module}' (in '{source}')") from e
        try:
            source = getattr(mod, name)
        except AttributeError as e:
            raise ValueError(
                f"dates: workalendar.{module} has no calendar '{name}'") from e
    return source() if isinstance(source, type) else source


def _years(years):
    return [years] if isinstance(years, int) else list(years)


def from_workalendar(source, years, *, weekend=None, hours=None) -> Calendar:
    """Build a :class:`Calendar` from a workalendar calendar over ``years``.

    ``source`` is a workalendar calendar class, an instance, or the dotted
    string ``"usa.UnitedStates"``; ``years`` is a year or an iterable of them. **Bound the range you ask for** -- a calendar
    holds the days it was given, so a load that runs into 2030 needs 2030 in
    this list. Asking for too few years is the failure mode, and it is silent:
    an unlisted year simply has no holidays in it.

    There is no ``observe`` parameter, on purpose. workalendar already applies
    each jurisdiction's shifting rule and returns the *observed* days, so
    passing ``observe="nearest"`` on top would shift the shifted day again --
    July 4th 2026 falls on a Saturday, workalendar hands back Friday the 3rd,
    and a second pass would add Thursday the 2nd as well. Use
    :func:`etools.dates.calendar` with ``observe`` when the holidays are your
    own unshifted data; use this when they are workalendar's.
    """
    cal = _instance(source)
    days = []
    for y in _years(years):
        days.extend(day for day, _label in cal.holidays(y))

    if weekend is None:
        # workalendar states the weekend per jurisdiction as weekday indices
        # (Friday/Saturday across much of the Gulf, not Saturday/Sunday).
        # Taking Sat/Sun as read would be wrong in exactly the places where
        # getting it wrong is most expensive.
        try:
            weekend = tuple(DAY_NAMES[i].lower() for i in cal.get_weekend_days())
        except Exception:                       # pragma: no cover - older API
            weekend = ("saturday", "sunday")

    return calendar(weekend=weekend, holidays=days, hours=hours)


def labels(source, years) -> dict:
    """``{day: label}`` for the same range -- why a day is not a working day.

    ``is_business_day`` answers whether; this answers why, which is what an
    operator reads at 6pm when a load did not run.
    """
    cal = _instance(source)
    return {day: label for y in _years(years) for day, label in cal.holidays(y)}
