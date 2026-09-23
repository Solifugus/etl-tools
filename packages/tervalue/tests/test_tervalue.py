# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""The kernel's suite. Every test names the axiom or defect it defends."""

from __future__ import annotations

import copy
import pickle
import unittest
from decimal import Decimal

from tervalue import (UNKNOWN, CurrencyMismatch, LossReport, Money, Outcome,
                      exponent)


class UnknownTests(unittest.TestCase):
    def test_it_is_one_object_through_copy_and_pickle(self):
        self.assertIs(copy.deepcopy(UNKNOWN), UNKNOWN)
        self.assertIs(pickle.loads(pickle.dumps(UNKNOWN)), UNKNOWN)
        self.assertIs(copy.copy(UNKNOWN), UNKNOWN)

    def test_it_is_not_none(self):
        """Axiom 7. None means 'not supplied'; this means 'not determined'."""
        self.assertIsNot(UNKNOWN, None)
        self.assertNotEqual(UNKNOWN, None)

    def test_arithmetic_propagates_because_that_is_the_true_answer(self):
        for got in (UNKNOWN + 1, 1 + UNKNOWN, UNKNOWN * 2, -UNKNOWN,
                    abs(UNKNOWN), UNKNOWN / 3, round(UNKNOWN)):
            self.assertIs(got, UNKNOWN)

    def test_bool_refuses_rather_than_silently_meaning_false(self):
        """Axiom 6. 'if x:' would take the false branch without saying so."""
        with self.assertRaises(TypeError) as cm:
            bool(UNKNOWN)
        self.assertIn("is UNKNOWN", str(cm.exception))


class MoneyTests(unittest.TestCase):
    def test_defect_1_the_int64_range_is_reachable(self):
        """The value gBASIC's own constructor could not express."""
        m = Money.of("92233720368547.75", "USD")
        self.assertEqual(m.minor, 9223372036854775)
        self.assertEqual(str(m.amount), "92233720368547.75")

    def test_defect_1_what_a_float_would_have_cost(self):
        """Not every decimal survives a float, and the ones that do not are
        ordinary. 92233720368547.75 happens to be exactly representable;
        two cents away it is not, and 1.005 is not either."""
        self.assertNotEqual(Decimal(92233720368547.77),
                            Decimal("92233720368547.77"))
        self.assertNotEqual(Decimal(1.005), Decimal("1.005"))
        self.assertEqual(Money.of("92233720368547.77", "USD").minor,
                         9223372036854777)
        self.assertEqual(Money.of("1.005", "USD").minor, 100)  # half-even

    def test_defect_1_float_is_refused_at_construction(self):
        with self.assertRaises(TypeError):
            Money.of(12.34, "USD")

    def test_defect_2_scaling_stays_in_exact_arithmetic(self):
        self.assertEqual(Money.of("0.10", "USD") * 3, Money.of("0.30", "USD"))
        self.assertEqual(Money.of("10.00", "USD") * Decimal("1.075"),
                         Money.of("10.75", "USD"))
        with self.assertRaises(TypeError):
            Money.of("1.00", "USD") * 1.5

    def test_defect_3_scale_comes_from_the_currency(self):
        self.assertEqual(exponent("JPY"), 0)
        self.assertEqual(exponent("KWD"), 3)
        self.assertEqual(exponent("USD"), 2)
        self.assertEqual(Money.of("1234", "JPY").minor, 1234)
        self.assertEqual(Money.of("1.234", "KWD").minor, 1234)

    def test_defect_4_the_rounding_rule_is_the_stated_one(self):
        """Half-even, on the text, not on a binary approximation of it."""
        self.assertEqual(Money.of("0.125", "USD").minor, 12)
        self.assertEqual(Money.of("0.135", "USD").minor, 14)
        self.assertEqual(Money.of("0.145", "USD").minor, 14)

    def test_accumulation_is_exact(self):
        total = Money.zero("USD")
        for _ in range(1000):
            total += Money.of("0.01", "USD")
        self.assertEqual(total, Money.of("10.00", "USD"))

    def test_currencies_do_not_mix(self):
        for op in (lambda: Money.of("1", "USD") + Money.of("1", "EUR"),
                   lambda: Money.of("1", "USD") - Money.of("1", "EUR"),
                   lambda: Money.of("1", "USD") < Money.of("1", "EUR")):
            with self.assertRaises(CurrencyMismatch):
                op()

    def test_equality_is_by_currency_too(self):
        self.assertNotEqual(Money.of("1.00", "USD"), Money.of("1.00", "CAD"))
        self.assertEqual(Money.of("1.00", "USD"), Money.of("1.00", "usd"))

    def test_immutable(self):
        with self.assertRaises(AttributeError):
            Money.of("1", "USD")._minor = 5

    def test_allocate_loses_no_minor_units(self):
        """100 three ways is the canonical cent-losing case."""
        parts = Money.of("100.00", "USD").allocate([1, 1, 1])
        self.assertEqual([p.minor for p in parts], [3334, 3333, 3333])
        self.assertEqual(sum(p.minor for p in parts), 10000)

    def test_allocate_by_weight_and_for_negatives(self):
        parts = Money.of("100.00", "USD").allocate([3, 1])
        self.assertEqual([str(p.amount) for p in parts], ["75.00", "25.00"])
        neg = Money.of("-0.05", "USD").split(3)
        self.assertEqual(sum(p.minor for p in neg), -5)

    def test_split_of_an_indivisible_amount_still_balances(self):
        for n in range(1, 13):
            parts = Money.of("0.01", "USD").split(n)
            self.assertEqual(sum(p.minor for p in parts), 1, f"n={n}")


class OutcomeTests(unittest.TestCase):
    def test_the_three_statuses_are_distinct(self):
        self.assertTrue(Outcome.ok(1).is_ok)
        self.assertTrue(Outcome.unknown(raw="  ").is_unknown)
        self.assertTrue(Outcome.invalid("bad date", raw="32/13").is_invalid)

    def test_an_invalid_must_say_how(self):
        """'This is wrong' without 'how' cannot be acted on."""
        with self.assertRaises(ValueError):
            Outcome("invalid", raw="x")

    def test_raw_is_kept_on_every_status(self):
        """Axiom 1: a value that could not be read is still shown to a person."""
        for o in (Outcome.ok(1, raw="1"), Outcome.unknown(raw="?"),
                  Outcome.invalid("nope", raw="!!")):
            self.assertIsNotNone(o.raw)

    def test_unknown_and_invalid_both_carry_UNKNOWN_not_None(self):
        self.assertIs(Outcome.unknown(raw="").value, UNKNOWN)
        self.assertIs(Outcome.invalid("x", raw="").value, UNKNOWN)

    def test_bool_refuses_because_it_would_merge_two_answers(self):
        with self.assertRaises(TypeError):
            bool(Outcome.unknown(raw=""))

    def test_unwrap_raises_only_for_the_caller_who_asked(self):
        self.assertEqual(Outcome.ok(7).unwrap(), 7)
        with self.assertRaises(ValueError):
            Outcome.invalid("bad", raw="x").unwrap()
        self.assertEqual(Outcome.invalid("bad", raw="x").or_else(0), 0)

    def test_map_passes_unknown_and_invalid_through_untouched(self):
        self.assertEqual(Outcome.ok(2).map(lambda v: v * 3).value, 6)
        bad = Outcome.invalid("bad", raw="x")
        self.assertIs(bad.map(lambda v: v * 3), bad)

    def test_source_does_not_affect_equality(self):
        self.assertEqual(Outcome.ok(1, "1", source="a"),
                         Outcome.ok(1, "1", source="b"))


class LossReportTests(unittest.TestCase):
    def test_empty_is_the_honest_common_case(self):
        self.assertTrue(LossReport.none().lossless)
        self.assertEqual(len(LossReport.none()), 0)
        self.assertEqual(str(LossReport.none()), "no loss")

    def test_losses_accumulate_and_merge(self):
        a = LossReport.none().plus("rounded", "0.005 dropped", "amount")
        b = LossReport.none().plus("truncated", "name over 22 bytes", "payee")
        both = a.merge(b)
        self.assertEqual(len(both), 2)
        self.assertEqual(len(a), 1, "merge must not mutate its operands")
        self.assertEqual(both.of_kind("rounded")[0].where, "amount")

    def test_bool_refuses_because_it_reads_both_ways(self):
        with self.assertRaises(TypeError):
            bool(LossReport.none())

    def test_it_reads_back_to_a_person(self):
        r = LossReport.none().plus("narrowed", "DECIMAL(19,4) to double", "bal")
        self.assertEqual(str(r), "narrowed at bal: DECIMAL(19,4) to double")


if __name__ == "__main__":
    unittest.main()
