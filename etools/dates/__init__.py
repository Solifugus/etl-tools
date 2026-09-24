# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Business calendars, day arithmetic, and a recurrence vocabulary.

A port of gBASIC's ``stdlib/dates.bas`` under the translation law
(``docs/porting-plan.md`` §1.1): same function names, same argument order,
same error text, so that learning one teaches the other.

Three things are adopted from Python rather than ported, per the roadmap's
selection rule -- build only what Python has no strong contender for:

* **the datetime kind itself** is stdlib ``date``/``datetime``. gBASIC carries
  precision inside one kind; Python's date/datetime split covers the only
  precision boundary used here, day versus finer, and a ``date`` *is* the
  day-precision value.
* **exact durations** are ``timedelta``.
* **holiday data** is workalendar, behind the ``calendars`` extra and an
  explicit conversion -- see :mod:`etools.dates.holidays`.

What is built is what Python does not answer: calendars as passed-around
data, business-day and business-hours arithmetic, and one spec vocabulary
served by three verbs.

    >>> from etools.dates import calendar, select, series
    >>> cal = calendar(holidays=["2026-07-03"], hours={"open": "9:00", "close": "17:00"})
    >>> select({"nth": 3, "weekday": "thursday", "within": "month"}, "2026-09-01")
    datetime.date(2026, 9, 17)
    >>> series({"every": "month", "when": {"nth": 3, "weekday": "thursday"},
    ...         "at": "14:00"},
    ...        {"from": "2026-01-01", "count": 3}, cal)[0]
    datetime.datetime(2026, 1, 15, 14, 0)

Two upstream defects this port found, both the same shape -- gBASIC's
``dates.bas`` guesses where eleven of its sibling libraries refuse:

1. unknown keys in a calendar spec or a selector spec are silently ignored,
   so ``{"nth": 3, "weekdy": "thursday"}`` quietly becomes "the third day of
   the month";
2. ``nth`` accepts *any* string as "last", so ``nth: "first"`` means last.

Both are refusals here. The fixes belong upstream in gBASIC.
"""

from ._calendar import (DEFAULT, Calendar, Hours, add_business_days,
                        business_days_between, calendar, is_business_day,
                        merge, next_business_day, previous_business_day)
from ._core import (DAY_NAMES, add_months, as_day, as_moment, at, between,
                    dayname, days_between, end_of_month, next_weekday,
                    previous_weekday, start_of_month, time_of_day)
from ._hours import (add_business_hours, business_hours_between,
                     is_business_time)
from ._select import matches, select, series

__all__ = [
    "DAY_NAMES", "DEFAULT", "Calendar", "Hours",
    "add_business_days", "add_business_hours", "add_months", "as_day",
    "as_moment", "at", "between", "business_days_between",
    "business_hours_between", "calendar", "dayname", "days_between",
    "end_of_month", "is_business_day", "is_business_time", "matches", "merge",
    "next_business_day", "next_weekday", "previous_business_day",
    "previous_weekday", "select", "series", "start_of_month", "time_of_day",
]
