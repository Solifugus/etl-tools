# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Business-hours arithmetic: working time that pauses overnight.

"Respond within 4 business hours" is :func:`add_business_hours`; "how much
working time elapsed" is :func:`business_hours_between`. Both need a calendar
carrying ``hours``.

The rules, decided rather than discovered (``datetime_design.md`` §9):

* a clock STARTING outside working hours starts at the next open -- and,
  going backward, at the previous close;
* a deadline that exhausts its time EXACTLY at close lands AT close. Rolling
  it to the next morning would silently extend an SLA, and landing at close
  is what makes the round-trip law hold::

      business_hours_between(a, add_business_hours(a, n, cal), cal) == n

* durations must be exact -- a month of business hours has no meaning;
* a negative duration walks backward, which is the honest algebra.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ._calendar import (DEFAULT, is_business_day, next_business_day,
                        previous_business_day)
from ._core import as_day, as_moment, time_of_day

__all__ = ["add_business_hours", "business_hours_between", "is_business_time"]


def _need_hours(cal):
    cal = DEFAULT if cal is None else cal
    if cal.hours is None:
        raise ValueError("dates: business-hours arithmetic needs a calendar "
                         "with hours: { open:, close: }")
    return cal


def _day_open(d, cal) -> datetime:
    dd = as_day(d)
    return datetime(dd.year, dd.month, dd.day) + time_of_day(cal.hours.open)


def _day_close(d, cal) -> datetime:
    dd = as_day(d)
    return datetime(dd.year, dd.month, dd.day) + time_of_day(cal.hours.close)


def is_business_time(d, cal=None) -> bool:
    """Is this instant inside working hours on a business day?

    The window is half-open: the open instant is working time, the close
    instant is not. Otherwise a day would contain one second it counts twice.
    """
    cal = _need_hours(cal)
    m = as_moment(d)
    if not is_business_day(m, cal):
        return False
    return _day_open(m, cal) <= m < _day_close(m, cal)


def _clock_forward(m, cal) -> datetime:
    """The nearest working instant at or after m."""
    if is_business_day(m, cal):
        if m < _day_open(m, cal):
            return _day_open(m, cal)
        if m < _day_close(m, cal):
            return m
    return _day_open(next_business_day(m, cal), cal)


def _clock_backward(m, cal) -> datetime:
    """The nearest working instant at or before m (for negative durations)."""
    if is_business_day(m, cal):
        if m > _day_close(m, cal):
            return _day_close(m, cal)
        if m > _day_open(m, cal):
            return m
    return _day_close(previous_business_day(m, cal), cal)


def add_business_hours(d, dur, cal=None) -> datetime:
    """Move ``dur`` of working time from d. Negative walks backward."""
    cal = _need_hours(cal)
    if not isinstance(dur, timedelta):
        raise ValueError("dates: business-hours arithmetic needs an exact "
                         "duration; a month has no fixed length")
    remaining = dur.total_seconds()
    if remaining >= 0:
        cur = _clock_forward(as_moment(d), cal)
        for _ in range(10000):
            room = (_day_close(cur, cal) - cur).total_seconds()
            if remaining <= room:
                return cur + timedelta(seconds=remaining)
            remaining -= room
            cur = _day_open(next_business_day(cur, cal), cal)
    else:
        remaining = -remaining
        cur = _clock_backward(as_moment(d), cal)
        for _ in range(10000):
            room = (cur - _day_open(cur, cal)).total_seconds()
            if remaining <= room:
                return cur - timedelta(seconds=remaining)
            remaining -= room
            cur = _day_close(previous_business_day(cur, cal), cal)
    raise ValueError("dates: business-hours arithmetic exceeded 10000 working days")


def business_hours_between(a, b, cal=None) -> timedelta:
    """Working time elapsed over (a, b), as an exact duration. Signed.

    Each business day contributes the overlap of [a, b] with its own working
    window, so a weekend or a holiday in the middle contributes nothing and
    an instant outside hours contributes nothing either.
    """
    cal = _need_hours(cal)
    aa, bb = as_moment(a), as_moment(b)
    if bb < aa:
        return -business_hours_between(b, a, cal)
    total = 0.0
    dd = as_day(aa)
    last = as_day(bb)
    while dd <= last:
        if is_business_day(dd, cal):
            seg_start = max(_day_open(dd, cal), aa)
            seg_end = min(_day_close(dd, cal), bb)
            if seg_end > seg_start:
                total += (seg_end - seg_start).total_seconds()
        dd += timedelta(days=1)
    return timedelta(seconds=total)
