# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Tests for etools.dates.

Every fixed point here is one gBASIC's own ``examples/dates_*_test.bas``
already asserts and passes, so a disagreement is a port defect rather than a
fresh guess about what the right answer is.

The hand-checkable anchors: 2026-08-17 is a Monday, so August 2026 has
Thursdays on 6/13/20/27, Wednesdays on 5/12/19/26 and Tuesdays on
4/11/18/25. 2026-01-01 is a Thursday, Christmas 2026 is a Friday, and
2026-10-31 is a Saturday.
"""

import unittest
from datetime import date, datetime, timedelta

from tervalue import UNKNOWN

from etools import dates as D

AUG = date(2026, 8, 17)          # a Monday
CAL = D.calendar()
XMAS = D.calendar(holidays=["2026-12-25"])
HOURS = D.calendar(hours={"open": "9:00", "close": "17:00"})
XMAS_HOURS = D.calendar(holidays=["2026-12-25"],
                        hours={"open": "9:00", "close": "17:00"})


class TestDayArithmetic(unittest.TestCase):
    def test_dayname_is_locale_independent(self):
        # A spec written weekday: "thursday" must mean Thursday on a machine
        # set to fr_FR, so the names are ours, not the locale's.
        self.assertEqual(D.dayname("2026-08-17"), "Monday")
        self.assertEqual(D.dayname(datetime(2026, 8, 17, 23, 59)), "Monday")

    def test_days_between_is_signed(self):
        self.assertEqual(D.days_between("2026-08-17", "2026-08-20"), 3)
        self.assertEqual(D.days_between("2026-08-20", "2026-08-17"), -3)
        self.assertEqual(D.days_between("2026-08-17", "2026-08-17"), 0)

    def test_add_months_clamps_the_day(self):
        # The accountant's rule: month first, THEN clamp. Jan 31 + 1 month is
        # Feb 28, not Mar 3 -- which is what gBASIC did before the redesign.
        self.assertEqual(D.add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(D.add_months(date(2026, 3, 31), 1), date(2026, 4, 30))
        self.assertEqual(D.add_months(date(2024, 2, 29), 12), date(2025, 2, 28))

    def test_between_months_agrees_with_the_clamp(self):
        # Jan 31 -> Feb 28 is one month, exactly as Jan 31 + 1 month is Feb 28.
        # If these two disagreed, month arithmetic would not round-trip.
        self.assertEqual(D.between("2026-01-31", "2026-02-28", "months"), 1)
        self.assertEqual(D.between("2026-01-31", "2026-02-27", "months"), 0)
        self.assertEqual(D.between("2026-01-01", "2027-01-01", "years"), 1)
        self.assertEqual(D.between("2026-02-28", "2026-01-31", "months"), -1)

    def test_between_refuses_an_unknown_unit(self):
        with self.assertRaises(ValueError) as cm:
            D.between("2026-01-01", "2026-02-01", "weeks")
        self.assertEqual(str(cm.exception),
                         "dates.between: unit must be days, months, or years")

    def test_at_midnight_keeps_day_precision(self):
        # Adding a zero duration does not bump precision in gBASIC; a date is
        # how Python spells that. A midnight stamp renders without a time.
        self.assertEqual(D.at("2026-08-17", "0:00"), date(2026, 8, 17))
        self.assertEqual(D.at("2026-08-17", "14:00"), datetime(2026, 8, 17, 14, 0))
        self.assertEqual(D.at("2026-08-17", timedelta(hours=9, minutes=30)),
                         datetime(2026, 8, 17, 9, 30))

    def test_next_weekday_is_strict(self):
        # From a Friday, next friday is seven days on. The trap that the
        # after:/on_or_after: spec names exist to avoid reproducing.
        fri = date(2026, 8, 21)
        self.assertEqual(D.next_weekday(fri, "friday"), date(2026, 8, 28))
        self.assertEqual(D.previous_weekday(fri, "friday"), date(2026, 8, 14))
        self.assertEqual(D.next_weekday(AUG, "friday"), date(2026, 8, 21))

    def test_month_ends(self):
        self.assertEqual(D.end_of_month("2026-02-10"), date(2026, 2, 28))
        self.assertEqual(D.start_of_month("2026-02-10"), date(2026, 2, 1))


class TestCalendar(unittest.TestCase):
    def test_default_is_sat_sun_no_holidays(self):
        self.assertTrue(D.is_business_day("2026-08-21"))       # Friday
        self.assertFalse(D.is_business_day("2026-08-22"))      # Saturday

    def test_holidays_normalise_to_day_precision(self):
        # A holiday supplied as a full timestamp still blocks the whole day.
        # Normalised once in the constructor, so membership never hits the
        # precision rule at call time.
        cal = D.calendar(holidays=[datetime(2026, 12, 25, 9, 30)])
        self.assertFalse(D.is_business_day("2026-12-25", cal))
        self.assertIn(date(2026, 12, 25), cal.holidays)

    def test_unknown_calendar_key_is_refused(self):
        # gBASIC ignores it silently and hands back a calendar with no
        # holidays; keyword-only arguments refuse it by construction. Upstream
        # defect, recorded in the module docstring.
        with self.assertRaises(TypeError):
            D.calendar(holidayz=["2026-12-25"])

    def test_unknown_weekday_is_refused(self):
        with self.assertRaises(ValueError):
            D.calendar(weekend=["saturday", "sundy"])

    def test_observe_nearest_is_the_us_federal_rule(self):
        # July 4 2026 is a Saturday, so the day off moves BACK to Friday the
        # 3rd. The original stays in the list -- it is already non-working.
        cal = D.calendar(holidays=["2026-07-04"], observe="nearest")
        self.assertIn(date(2026, 7, 3), cal.holidays)
        self.assertIn(date(2026, 7, 4), cal.holidays)
        self.assertFalse(D.is_business_day("2026-07-03", cal))

    def test_observe_forward_is_the_uk_substitute_day(self):
        cal = D.calendar(holidays=["2026-07-04"], observe="forward")
        self.assertIn(date(2026, 7, 6), cal.holidays)
        self.assertNotIn(date(2026, 7, 3), cal.holidays)

    def test_observe_chains_rather_than_colliding(self):
        # Boxing Day 2026 is a Saturday and the 27th a Sunday; observing
        # forward must take Monday AND Tuesday, not Monday twice.
        cal = D.calendar(holidays=["2026-12-26", "2026-12-27"], observe="forward")
        self.assertIn(date(2026, 12, 28), cal.holidays)
        self.assertIn(date(2026, 12, 29), cal.holidays)

    def test_observe_refuses_an_unknown_rule(self):
        with self.assertRaises(ValueError) as cm:
            D.calendar(holidays=["2026-07-04"], observe="sideways")
        self.assertEqual(str(cm.exception),
                         "dates: observe must be nearest or forward")

    def test_business_day_steps_are_strict(self):
        # next_business_day is strictly after, even from a business day.
        self.assertEqual(D.next_business_day("2026-08-17"), date(2026, 8, 18))
        self.assertEqual(D.next_business_day("2026-08-21"), date(2026, 8, 24))
        self.assertEqual(D.previous_business_day("2026-08-24"), date(2026, 8, 21))

    def test_add_business_days_signed_and_zero(self):
        self.assertEqual(D.add_business_days("2026-08-17", 5), date(2026, 8, 24))
        self.assertEqual(D.add_business_days("2026-08-24", -5), date(2026, 8, 17))
        self.assertEqual(D.add_business_days("2026-08-22", 0), date(2026, 8, 22))

    def test_business_days_between_is_half_open(self):
        # Business days d with a < d <= b. Stated, because half-open intervals
        # are where calendar bugs live.
        self.assertEqual(D.business_days_between("2026-08-17", "2026-08-21"), 4)
        self.assertEqual(D.business_days_between("2026-08-21", "2026-08-17"), -4)
        self.assertEqual(D.business_days_between("2026-08-17", "2026-08-17"), 0)
        self.assertEqual(D.business_days_between("2026-12-24", "2026-12-28", XMAS), 1)

    def test_an_empty_calendar_refuses_rather_than_hangs(self):
        # merge can legitimately produce this. A hang is the least debuggable
        # outcome there is, so the guard turns it into a sentence.
        never = D.calendar(weekend=[n.lower() for n in D.DAY_NAMES])
        with self.assertRaises(ValueError) as cm:
            D.next_business_day("2026-08-17", never)
        self.assertEqual(str(cm.exception),
                         "dates: no business day within 10 years; is the calendar empty?")

    def test_merge_is_a_union_of_constraints(self):
        # The law that makes merging testable by arithmetic:
        #   is_business_day(d, merge([a,b])) == is_business_day(d,a) and (...,b)
        a = D.calendar(holidays=["2026-08-18"])
        b = D.calendar(weekend=["friday", "saturday"], holidays=["2026-08-19"])
        both = D.merge([a, b])
        day = date(2026, 8, 14)
        for _ in range(30):
            self.assertEqual(
                D.is_business_day(day, both),
                D.is_business_day(day, a) and D.is_business_day(day, b),
                f"merge law broken at {day}")
            day += timedelta(days=1)

    def test_merge_intersects_hours_and_never_raises(self):
        a = D.calendar(hours={"open": "9:00", "close": "17:00"})
        b = D.calendar(hours={"open": "10:00", "close": "16:00"})
        self.assertEqual(D.merge([a, b]).hours, D.Hours("10:00", "16:00"))
        # An empty window is legitimate -- one calendar closes before the
        # other opens. Consumers handle it; merge does not raise.
        c = D.calendar(hours={"open": "18:00", "close": "20:00"})
        self.assertEqual(D.merge([a, c]).hours, D.Hours("18:00", "17:00"))


class TestSelect(unittest.TestCase):
    """Fixed points taken from gBASIC's examples/dates_select_test.bas."""

    def test_nth_within_a_scope(self):
        self.assertEqual(D.select({"nth": 3, "weekday": "thursday", "within": "month"}, AUG),
                         date(2026, 8, 20))
        self.assertEqual(D.select({"nth": "last", "weekday": "wednesday", "within": "month"}, AUG),
                         date(2026, 8, 26))
        self.assertEqual(D.select({"nth": -1, "weekday": "wednesday", "within": "month"}, AUG),
                         date(2026, 8, 26))
        self.assertEqual(D.select({"nth": 1, "weekday": "monday", "within": "quarter"}, AUG),
                         date(2026, 7, 6))
        self.assertEqual(D.select({"nth": 1, "weekday": "friday", "within": "year"}, AUG),
                         date(2026, 1, 2))
        self.assertEqual(D.select({"nth": -1, "kind": "business", "within": "week"},
                                  date(2026, 8, 19)), date(2026, 8, 21))

    def test_a_miss_is_unknown_not_an_error(self):
        # August 2026 has four Tuesdays. Scheduling code probes for exactly
        # this, so a miss is absent information rather than a mistake -- and
        # a malformed spec still raises, because they mean different things.
        self.assertIs(D.select({"nth": 5, "weekday": "tuesday", "within": "month"}, AUG),
                      UNKNOWN)

    def test_strictness_is_in_the_name(self):
        self.assertEqual(D.select({"nth": 1, "weekday": "tuesday", "after": {"day": 15}}, AUG),
                         date(2026, 8, 18))
        self.assertEqual(D.select({"nth": 1, "weekday": "monday", "on_or_after": AUG}, AUG),
                         date(2026, 8, 17))
        self.assertEqual(D.select({"weekday": "monday", "after": AUG}, AUG),
                         date(2026, 8, 24))
        # A bare spec reads as "next X" -- strictly after the anchor.
        self.assertEqual(D.select({"weekday": "friday"}, AUG), date(2026, 8, 21))

    def test_first_business_day_before_a_deadline(self):
        self.assertEqual(
            D.select({"nth": 1, "kind": "business", "before": date(2026, 12, 28)},
                     date(2026, 12, 28), XMAS),
            date(2026, 12, 24))

    def test_roll_modified_keeps_the_payment_in_its_month(self):
        # Oct 31 2026 is a Saturday. "modified" goes forward unless that
        # crosses into November -- which it does, so it goes back.
        oct15 = date(2026, 10, 15)
        self.assertEqual(
            D.select({"nth": 1, "day": 31, "within": "month", "roll": "modified"}, oct15),
            date(2026, 10, 30))
        self.assertEqual(
            D.select({"nth": 1, "day": 31, "within": "month", "roll": "forward"}, oct15),
            date(2026, 11, 2))

    def test_roll_refuses_an_unknown_convention(self):
        with self.assertRaises(ValueError) as cm:
            D.select({"nth": 1, "day": 31, "within": "month", "roll": "sideways"},
                     date(2026, 10, 15))
        self.assertEqual(str(cm.exception),
                         "dates: roll must be forward, backward, or modified")

    def test_nth_must_be_positive_when_searching_from_an_anchor(self):
        with self.assertRaises(ValueError) as cm:
            D.select({"nth": -1, "weekday": "monday", "after": AUG}, AUG)
        self.assertEqual(
            str(cm.exception),
            "dates.select: nth must be positive when searching from an anchor")

    def test_within_needs_an_nth(self):
        with self.assertRaises(ValueError) as cm:
            D.select({"weekday": "monday", "within": "month"}, AUG)
        self.assertEqual(
            str(cm.exception),
            "dates.select: nth is required with within (or use after/before)")

    def test_within_refuses_an_unknown_scope(self):
        with self.assertRaises(ValueError) as cm:
            D.select({"nth": 1, "weekday": "monday", "within": "fortnight"}, AUG)
        self.assertEqual(str(cm.exception),
                         "dates: within must be week, month, quarter, or year")

    def test_a_misspelled_spec_field_is_refused(self):
        # gBASIC reads specs with has(), so this quietly becomes "the third
        # day of the month" -- while eleven sibling libraries refuse unknown
        # options through _options(). Upstream defect; a refusal here.
        with self.assertRaises(ValueError) as cm:
            D.select({"nth": 3, "weekdy": "thursday", "within": "month"}, AUG)
        self.assertIn("unknown spec field 'weekdy'", str(cm.exception))

    def test_nth_accepts_only_last_as_a_word(self):
        # gBASIC returns -1 for ANY string, so nth: "first" silently means
        # last. Second upstream defect found by this port.
        with self.assertRaises(ValueError) as cm:
            D.select({"nth": "first", "weekday": "thursday", "within": "month"}, AUG)
        self.assertIn('nth must be a number or "last"', str(cm.exception))


class TestMatches(unittest.TestCase):
    def test_matches_is_the_same_vocabulary_as_a_predicate(self):
        rule = {"nth": 3, "weekday": "thursday", "within": "month"}
        self.assertTrue(D.matches(date(2026, 8, 20), rule))
        self.assertFalse(D.matches(date(2026, 8, 13), rule))
        self.assertFalse(D.matches(date(2026, 8, 15), {"kind": "business"}))

    def test_matches_agrees_with_select_across_a_year(self):
        # The property that makes the two verbs verify each other: the day
        # select returns for a month is the only day in it that matches.
        rule = {"nth": 3, "weekday": "thursday", "within": "month"}
        for month in range(1, 13):
            anchor = date(2026, month, 1)
            chosen = D.select(rule, anchor)
            day = anchor
            while day.month == month:
                self.assertEqual(D.matches(day, rule), day == chosen,
                                 f"{day} disagrees with select")
                day += timedelta(days=1)


class TestSeries(unittest.TestCase):
    """Fixed points taken from gBASIC's examples/dates_select_test.bas."""

    BOARD = {"every": "month", "when": {"nth": 3, "weekday": "thursday"},
             "at": "14:00"}

    def test_period_mode_stamps_the_time(self):
        meetings = D.series(self.BOARD,
                            {"from": "2026-01-01", "through": "2026-06-30"})
        self.assertEqual(len(meetings), 6)
        self.assertEqual(meetings[0], datetime(2026, 1, 15, 14, 0))

    def test_every_emitted_day_matches_the_rule(self):
        meetings = D.series(self.BOARD,
                            {"from": "2026-01-01", "through": "2026-06-30"})
        rule = {"nth": 3, "weekday": "thursday", "within": "month"}
        for m in meetings:
            self.assertTrue(D.matches(m, rule), f"{m} does not match")

    def test_except_leaves_a_gap_not_a_reschedule(self):
        trimmed = D.series({"every": "month",
                            "when": {"nth": 3, "weekday": "thursday"},
                            "except": [date(2026, 3, 19)]},
                           {"from": "2026-01-01", "through": "2026-06-30"})
        self.assertEqual(len(trimmed), 5)
        self.assertNotIn(date(2026, 3, 19), trimmed)

    def test_series_does_not_mutate_the_callers_spec(self):
        # gBASIC writes sub.within into the record it was handed. Here that
        # would leave "within" in a dict the caller may reuse, so the sub-rule
        # is copied. Cheap to get wrong, silent when wrong.
        when = {"nth": 3, "weekday": "thursday"}
        spec = {"every": "month", "when": when}
        D.series(spec, {"from": "2026-01-01", "count": 2})
        self.assertEqual(when, {"nth": 3, "weekday": "thursday"})

    def test_payroll_rolls_off_holidays(self):
        pcal = D.calendar(holidays=["2026-02-13"])
        paydays = D.series({"every": timedelta(weeks=2), "roll": "backward"},
                           {"from": "2026-01-02", "count": 6}, pcal)
        self.assertEqual(len(paydays), 6)
        self.assertEqual(paydays[3], date(2026, 2, 12))
        self.assertEqual(paydays[4], date(2026, 2, 27))
        for p in paydays:
            self.assertTrue(D.is_business_day(p, pcal), f"{p} is not a working day")

    def test_monthly_stepping_is_multiplicative_not_cumulative(self):
        # Jan 31 -> Feb 28 -> MAR 31. Cumulative clamping would give
        # Feb-28-forever, which is the classic month-end drift bug.
        ends = D.series({"every": "month"}, {"from": "2026-01-31", "count": 4})
        self.assertEqual(ends[1], date(2026, 2, 28))
        self.assertEqual(ends[2], date(2026, 3, 31))
        self.assertEqual(ends[3], date(2026, 4, 30))

    def test_when_without_nth_emits_every_candidate(self):
        # Mon/Wed/Fri standups: RRULE's FREQ=WEEKLY;BYDAY=MO,WE,FR without
        # the grammar.
        stand = D.series({"every": "week",
                          "when": {"weekday": ["monday", "wednesday", "friday"]}},
                         {"from": AUG, "count": 6})
        self.assertEqual(len(stand), 6)
        self.assertEqual(stand[0], date(2026, 8, 17))
        self.assertEqual(stand[3], date(2026, 8, 24))

    def test_month_list_is_bymonth(self):
        mid = D.series({"every": "month", "when": {"day": 15, "month": [1, 7]}},
                       {"from": "2026-01-01", "through": "2026-12-31"})
        self.assertEqual(mid, [date(2026, 1, 15), date(2026, 7, 15)])
        self.assertTrue(D.matches(mid[1], {"day": 15, "month": 7}))

    def test_business_day_stepping_skips_the_holiday(self):
        run = D.series({"every": "business day"},
                       {"from": "2026-12-23", "count": 3}, XMAS)
        self.assertEqual(run[2], date(2026, 12, 28))

    def test_bounds_need_an_end(self):
        with self.assertRaises(ValueError) as cm:
            D.series({"every": "month"}, {"from": "2026-01-01"})
        self.assertEqual(str(cm.exception),
                         "dates.series: bounds need through: or count:")

    def test_when_needs_a_period_unit(self):
        with self.assertRaises(ValueError) as cm:
            D.series({"every": "day", "when": {"weekday": "monday"}},
                     {"from": "2026-01-01", "count": 3})
        self.assertEqual(
            str(cm.exception),
            "dates.series: when: needs every: week, month, quarter, or year")

    def test_a_spec_needs_every(self):
        with self.assertRaises(ValueError) as cm:
            D.series({"weekday": "monday"}, {"from": "2026-01-01", "count": 3})
        self.assertEqual(str(cm.exception),
                         "dates.series: spec needs every: (or when: with every:)")

    def test_zero_step_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            D.series({"every": timedelta(0)}, {"from": "2026-01-01", "count": 3})
        self.assertEqual(str(cm.exception), "dates.series: every cannot be zero")

    def test_unknown_step_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            D.series({"every": "fortnight"}, {"from": "2026-01-01", "count": 3})
        self.assertEqual(str(cm.exception),
                         "dates.series: every must be a duration or one of "
                         "day, week, month, quarter, year, business day")

    def test_unknown_bounds_field_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            D.series({"every": "month"}, {"from": "2026-01-01", "to": "2026-06-30"})
        self.assertIn("unknown bounds field 'to'", str(cm.exception))


class TestBusinessHours(unittest.TestCase):
    """Fixed points taken from gBASIC's examples/dates_hours_test.bas."""

    def test_the_sla_shape(self):
        self.assertEqual(D.add_business_hours("2026-08-17 13:00", timedelta(hours=4), HOURS),
                         datetime(2026, 8, 17, 17, 0))
        self.assertEqual(D.add_business_hours("2026-08-17 15:00", timedelta(hours=4), HOURS),
                         datetime(2026, 8, 18, 11, 0))
        self.assertEqual(D.add_business_hours("2026-08-17 09:00", timedelta(hours=8), HOURS),
                         datetime(2026, 8, 17, 17, 0))

    def test_exhausting_at_close_lands_at_close(self):
        # Rolling to the next morning would silently EXTEND an SLA, and
        # landing at close is what makes the round-trip law hold.
        self.assertEqual(D.add_business_hours("2026-08-17 13:00", timedelta(hours=4), HOURS),
                         datetime(2026, 8, 17, 17, 0))

    def test_a_clock_starting_outside_hours_starts_at_open(self):
        self.assertEqual(D.add_business_hours("2026-08-17 06:00", timedelta(hours=1), HOURS),
                         datetime(2026, 8, 17, 10, 0))
        self.assertEqual(D.add_business_hours("2026-08-15 11:00", timedelta(hours=1), HOURS),
                         datetime(2026, 8, 17, 10, 0))
        self.assertEqual(D.add_business_hours("2026-08-15 11:00", timedelta(0), HOURS),
                         datetime(2026, 8, 17, 9, 0))

    def test_weekends_and_holidays_pause_the_clock(self):
        self.assertEqual(D.add_business_hours("2026-08-14 16:00", timedelta(hours=4), HOURS),
                         datetime(2026, 8, 17, 12, 0))
        self.assertEqual(D.add_business_hours("2026-12-24 15:00", timedelta(hours=4), XMAS_HOURS),
                         datetime(2026, 12, 28, 11, 0))

    def test_negative_durations_walk_backward(self):
        self.assertEqual(D.add_business_hours("2026-08-17 10:00", timedelta(hours=-2), HOURS),
                         datetime(2026, 8, 14, 16, 0))

    def test_elapsed_working_time(self):
        self.assertEqual(D.business_hours_between("2026-08-17 15:00", "2026-08-18 11:00", HOURS),
                         timedelta(hours=4))
        self.assertEqual(D.business_hours_between("2026-08-14 15:00", "2026-08-17 11:00", HOURS),
                         timedelta(hours=4))
        self.assertEqual(D.business_hours_between("2026-08-17 13:00", "2026-08-17 13:00", HOURS),
                         timedelta(0))
        self.assertEqual(D.business_hours_between("2026-08-17 11:00", "2026-08-14 15:00", HOURS),
                         timedelta(hours=-4))
        # Time before the window opens counts as nothing at all.
        self.assertEqual(D.business_hours_between("2026-08-15 08:00", "2026-08-17 13:00", HOURS),
                         timedelta(hours=4))

    def test_the_round_trip_law(self):
        # business_hours_between(a, add_business_hours(a, n)) == n, which is
        # the load-bearing check: it is what "lands AT close" buys.
        a = datetime(2026, 8, 17, 10, 30)
        for n in (timedelta(hours=1), timedelta(hours=4),
                  timedelta(minutes=90), timedelta(hours=20)):
            self.assertEqual(D.business_hours_between(a, D.add_business_hours(a, n, HOURS), HOURS),
                             n, f"round trip broken for {n}")

    def test_the_window_is_half_open(self):
        # The open instant is working time; the close instant is not, or a
        # day would contain one second it counts twice.
        self.assertTrue(D.is_business_time("2026-08-17 10:00", HOURS))
        self.assertTrue(D.is_business_time("2026-08-17 09:00", HOURS))
        self.assertFalse(D.is_business_time("2026-08-17 17:00", HOURS))
        self.assertFalse(D.is_business_time("2026-08-15 11:00", HOURS))

    def test_hours_arithmetic_needs_a_calendar_with_hours(self):
        with self.assertRaises(ValueError) as cm:
            D.add_business_hours("2026-08-17 10:00", timedelta(hours=1), CAL)
        self.assertEqual(str(cm.exception),
                         "dates: business-hours arithmetic needs a calendar "
                         "with hours: { open:, close: }")

    def test_hours_arithmetic_needs_an_exact_duration(self):
        with self.assertRaises(ValueError) as cm:
            D.add_business_hours("2026-08-17 10:00", "1 month", HOURS)
        self.assertEqual(str(cm.exception),
                         "dates: business-hours arithmetic needs an exact "
                         "duration; a month has no fixed length")


try:
    from workalendar.usa import UnitedStates
    HAVE_WORKALENDAR = True
except ImportError:                              # pragma: no cover
    HAVE_WORKALENDAR = False


@unittest.skipUnless(HAVE_WORKALENDAR, "needs etools-etl[calendars]")
class TestWorkalendarAdapter(unittest.TestCase):
    def test_holidays_arrive_already_observed(self):
        # July 4 2026 is a Saturday. workalendar returns BOTH the actual day
        # and the observed Friday, which is why from_workalendar takes no
        # observe argument -- a second pass would shift the shifted day and
        # take Thursday the 2nd as well.
        from etools.dates import holidays
        cal = holidays.from_workalendar(UnitedStates, 2026)
        self.assertIn(date(2026, 7, 3), cal.holidays)
        self.assertIn(date(2026, 7, 4), cal.holidays)
        self.assertFalse(D.is_business_day("2026-07-03", cal))
        self.assertEqual(D.next_business_day("2026-07-02", cal), date(2026, 7, 6))

    def test_the_weekend_comes_from_the_jurisdiction(self):
        # Taking Sat/Sun as read would be wrong across much of the Gulf --
        # exactly where getting it wrong is most expensive.
        from workalendar.asia import Qatar

        from etools.dates import holidays
        self.assertEqual(holidays.from_workalendar(Qatar, 2026).weekend,
                         ("friday", "saturday"))

    def test_a_dotted_string_names_the_same_calendar(self):
        # Which country's calendar is data too -- it arrives from a config
        # file or a database column as often as from an import.
        from etools.dates import holidays
        self.assertEqual(holidays.from_workalendar("usa.UnitedStates", 2026),
                         holidays.from_workalendar(UnitedStates, 2026))

    def test_a_bad_dotted_string_names_what_is_wrong(self):
        from etools.dates import holidays
        for bad, expect in (("UnitedStates", "must be 'module.Class'"),
                            ("usa.Atlantis", "has no calendar 'Atlantis'"),
                            ("nowhere.Thing", "no workalendar region 'nowhere'")):
            with self.assertRaises(ValueError) as cm:
                holidays.from_workalendar(bad, 2026)
            self.assertIn(expect, str(cm.exception))

    def test_labels_say_why(self):
        from etools.dates import holidays
        labels = holidays.labels(UnitedStates, 2026)
        self.assertEqual(labels[date(2026, 7, 3)], "Independence Day (Observed)")


if __name__ == "__main__":
    unittest.main()
