# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Tests for arispec.

The end-to-end expectations are gBASIC's own golden files for the same
fixtures and the same specs, so a disagreement is a port defect rather than a
fresh guess about the right answer.

The unit tests below them are each a *measured* defect from the upstream
register -- every one of these returned a plausible wrong number before the
guard that now prevents it, and not one of them raised.
"""

import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

import arispec
from arispec import UNKNOWN
from arispec._recognize import _date_in, _decimal_in, _integer_in, _money_in

FIX = Path(__file__).parent / "fixtures"


def fixture(name):
    # gBASIC's harness reads with read_lines() and rejoins, dropping the
    # trailing newline. Matching that keeps the line counts comparable.
    return (FIX / name).read_text().rstrip("\n")


TELLER_SPEC = r'''
page:
    break: /^[0-9]{2}\/[0-9]{2}\/[0-9]{4} .*Page [0-9]+$/
    drop: 2

section report starts(/^Branch: /):
    field branch: right of "Branch:" as integer

    section tellers repeats starts(/^Teller: /):
        field name: between "Teller:" and "Teller #:"
        field teller_no: right of "Teller #:" as integer
        field beginning_cash: right of "Beginning Cash" as money
        field ending_cash: right of "Ending Cash" as money
        field total_trans: right of "Total Transactions" as money

        section detail starts(/^GL[ ]+Tran #/) ends(/^[ ]*$/):
            rows:
                field gl: columns 0-24
                field tran_no: columns 25-37
                field tran_ty: columns 38-43 as integer
                field amount: last money

    section closing repeats starts(/^Closing Cash in Drawer/):
        field teller_no: right of "Teller#:" as integer
        field hundreds: right of "Hundreds" as integer
        field dollars: right of "Dollars" within columns 26-79 as integer
        field bait_cash: right of "Bait Cash" as money
'''

GENERATED_SPEC = r'''
page:
    break: formfeed
    drop: 2

section report:
    section branches repeats starts(/^Branch: /):
        field branch_no: right of "Branch:" as integer
        field branch_total: right of /^Branch [0-9]+ Total/ as money

        section tellers repeats starts(/^Teller: /):
            field teller_no: right of "Teller #:" as integer
            field beginning_cash: right of "Beginning Cash" as money
            field ending_cash: right of "Ending Cash" as money
'''

DELINQUENCY_SPEC = r'''
section report:
    section regions repeats starts(/^REGION: /):
        field region: between "REGION:" and "REGION CODE:"
        field region_code: right of "REGION CODE:"

        section branches repeats starts(/^  BRANCH /):
            field branch_no: right of "BRANCH" as integer
            field officer: down 1 of "OFFICER"
            field branch_total: up 2 of "BRANCH TOTAL" as money
            field notes: right flush of /\.\.\.\. /
            field remarks: down 1-3 of "REMARKS:"

            section loans repeats starts(/^    ACCOUNT/) ends(/^[ ]*$|^    -+$/):
                rows continue(/^[ ]+COLLATERAL/):
                    field account: columns 4-18
                    field member: columns 19-45
                    field opened: columns 46-56 as date
                    field balance: last money
                    field collateral: right of "COLLATERAL:"
'''


class TestPageFurniture(unittest.TestCase):
    def test_a_recurring_header_is_stripped(self):
        report = fixture("teller_totals.rpt")
        clean = arispec.clean_grid(report, TELLER_SPEC)
        self.assertEqual(len(report.split("\n")), 76)
        self.assertEqual(len(clean), 72)
        self.assertEqual([l for l in clean if l.rstrip().endswith("Page 1")], [])

    def test_form_feeds_are_stripped(self):
        report = fixture("teller_totals_generated.rpt")
        clean = arispec.clean_grid(report, GENERATED_SPEC)
        self.assertEqual(len(report.split("\n")), 230)
        self.assertEqual(len(clean), 222)
        self.assertEqual([l for l in clean if "\f" in l], [])


class TestTellerFixture(unittest.TestCase):
    """The irregularity fixture. Golden: gBASIC examples/ari_teller_test.out."""

    @classmethod
    def setUpClass(cls):
        cls.r = arispec.parse(fixture("teller_totals.rpt"), TELLER_SPEC)
        cls.v = cls.r.value

    def test_it_parses(self):
        self.assertTrue(self.r.ok, self.r.message)
        self.assertEqual(self.v["branch"], 14)
        self.assertEqual(len(self.v["tellers"]), 3)

    def test_fields_are_anchored_by_label_not_row_offset(self):
        # THE CASE THAT MATTERS. Teller 386 prints Beginning/Ending/Total and
        # tellers 261 and 262 print Beginning/Total/Ending. A row-offset spec
        # reads the wrong number for two of the three and says nothing.
        want = {
            386: (Decimal("13586.25"), Decimal("-8651.75"), Decimal("56870.50")),
            261: (Decimal("3863.50"), Decimal("18510.75"), Decimal("66921.35")),
            262: (Decimal("3863.50"), Decimal("18510.75"), Decimal("66921.35")),
        }
        for t in self.v["tellers"]:
            b, e, tot = want[t["teller_no"]]
            self.assertEqual(t["beginning_cash"], b, t["teller_no"])
            self.assertEqual(t["ending_cash"], e, t["teller_no"])
            self.assertEqual(t["total_trans"], tot, t["teller_no"])

    def test_the_name_comes_out_between_two_labels(self):
        self.assertEqual(self.v["tellers"][0]["name"].strip(), "Wendy Hermin")

    def test_amount_is_found_by_type_not_by_column(self):
        # The Amount heading is four columns adrift of its own data, and the
        # negative row is one column wider than the positives because the
        # trailing minus is appended AFTER right-justification. Neither the
        # heading nor a fixed column can find it.
        rows = self.v["tellers"][0]["detail"]["rows"]
        self.assertEqual(rows["amount"], [Decimal("9250.00"), Decimal("18500.00"),
                                          Decimal("-6000.25")])

    def test_rows_are_a_frame(self):
        # Columns of equal length -- what polars.DataFrame and
        # pandas.DataFrame take directly, with no dependency on either.
        rows = self.v["tellers"][0]["detail"]["rows"]
        self.assertEqual(set(rows), {"gl", "tran_no", "tran_ty", "amount"})
        self.assertEqual({len(c) for c in rows.values()}, {3})
        self.assertEqual(rows["tran_ty"], [12, 11, 13])

    def test_the_heading_is_not_taken_as_a_data_row(self):
        # A section's own starts() line belongs to the section and is not
        # offered to its repeating children.
        rows = self.v["tellers"][2]["detail"]["rows"]
        self.assertEqual(len(rows["gl"]), 2)
        self.assertNotIn("GL", [g.strip() for g in rows["gl"]])

    def test_one_label_two_spellings(self):
        # `Teller #:` in the summary and `Teller#:` in the closing block are
        # the same field spelled two ways in one document. The spec says so;
        # there is no cleverness available and none needed.
        self.assertEqual([c["teller_no"] for c in self.v["closing"]], [386, 261, 262])

    def test_a_literal_anchor_does_not_match_inside_a_longer_word(self):
        # The grid holds both `Dollars` and `Half-Dollars`. `\b` would NOT
        # have helped -- a hyphen is a non-word character, so there IS a word
        # boundary between `-` and `D`. A column window is what settles it.
        self.assertEqual([c["dollars"] for c in self.v["closing"]], [1, 1, 1])

    def test_one_malformed_cell_becomes_unknown_alone(self):
        # `$8,0000` matches no money form. The cell is unknown; every other
        # field in the same record parses. Never a silent zero, never a raise
        # that sinks the import.
        for c in self.v["closing"]:
            self.assertIs(c["bait_cash"], UNKNOWN)
            self.assertEqual(c["hundreds"], 13)

    def test_the_unreadable_cell_is_reported(self):
        paths = {d["path"]: d["reason"] for d in self.r.diagnostics}
        self.assertTrue(any(p.endswith("bait_cash") for p in paths))
        self.assertIn("malformed-money", paths.values())


class TestGeneratedFixture(unittest.TestCase):
    """Golden: the second half of gBASIC examples/ari_teller_test.out."""

    @classmethod
    def setUpClass(cls):
        cls.r = arispec.parse(fixture("teller_totals_generated.rpt"), GENERATED_SPEC)

    def test_one_recognizer_reads_three_dialects(self):
        # Money format varies by the RUNTIME branch -- plain, then
        # symbol-with-inner-padding, then no-symbol-with-trailing-minus -- and
        # all three branches are instances of ONE section declaration, so a
        # lexical `using` cannot express it. The union recognizer must.
        want = [(14, Decimal("255894.00"), 261, Decimal("5755.75"), Decimal("-11653.25")),
                (21, Decimal("268344.00"), 301, Decimal("6045.75"), Decimal("-12113.25")),
                (28, Decimal("280794.00"), 341, Decimal("6335.75"), Decimal("-12573.25"))]
        self.assertEqual(len(self.r.value["branches"]), 3)
        for b, (no, total, tno, begin, end) in zip(self.r.value["branches"], want):
            self.assertEqual(b["branch_no"], no)
            self.assertEqual(b["branch_total"], total)
            self.assertEqual(len(b["tellers"]), 3)
            self.assertEqual(b["tellers"][0]["teller_no"], tno)
            self.assertEqual(b["tellers"][0]["beginning_cash"], begin)
            self.assertEqual(b["tellers"][0]["ending_cash"], end)


class TestDelinquencyFixture(unittest.TestCase):
    """The vertical-locator fixture. Golden: ari_delinquency_test.out."""

    @classmethod
    def setUpClass(cls):
        cls.r = arispec.parse(fixture("delinquency.rpt"), DELINQUENCY_SPEC)
        cls.b142 = cls.r.value["regions"][0]["branches"][0]

    def test_down_one_reads_the_line_below_a_lone_label(self):
        self.assertEqual(self.b142["officer"].strip(), "T. OKONKWO")

    def test_up_two_reads_an_amount_printed_above_its_label(self):
        self.assertEqual(self.b142["branch_total"], Decimal("90180.72"))

    def test_right_flush_reads_past_a_dotted_leader(self):
        self.assertEqual(self.b142["notes"].strip(), "SEE SCHEDULE B")

    def test_a_range_survives_a_gap_that_varies(self):
        # The gap between REMARKS: and its note is 1, 2, 2 and 3 lines across
        # the four branches, because the generator emits a varying number of
        # blank lines -- which is what real reports do. An exact distance
        # matches one branch and misses the rest, silently.
        remarks = [b["remarks"].strip()
                   for rg in self.r.value["regions"] for b in rg["branches"]]
        self.assertEqual(len(remarks), 4)
        self.assertTrue(all(remarks), f"a branch lost its remark: {remarks}")
        self.assertEqual(remarks[0], "Member contacted; promised payment.")

    def test_wrapped_records_absorb_their_continuation_line(self):
        # Every other row wraps onto a COLLATERAL line: one record, two
        # physical lines. Rows without a wrap leave collateral unknown, which
        # is correct and shows up as a diagnostic rather than a guess.
        rows = self.b142["loans"][0]["rows"]
        self.assertEqual(len(rows["account"]), 2)
        self.assertIn("1FTEW1E5XKKE81191", rows["collateral"][0])
        self.assertIs(rows["collateral"][1], UNKNOWN)

    def test_repeats_with_ends_finds_both_tables(self):
        # One instance could not distinguish "found them all" from "found the
        # first and stopped".
        self.assertEqual(len(self.b142["loans"]), 2)

    def test_the_ambiguous_date_minority_is_refused_not_guessed(self):
        # 07/12/2021 is 7 December and 12 July and nothing in the token says
        # which, so it is unknown. 23/06/2022 needs no declaration -- 23
        # cannot be a month.
        rows = self.b142["loans"][0]["rows"]
        self.assertIs(rows["opened"][0], UNKNOWN)
        self.assertEqual(rows["opened"][1], date(2022, 6, 23))
        reasons = {d["reason"] for d in self.r.diagnostics}
        self.assertIn("ambiguous-date", reasons)

    def test_parenthesised_amounts_are_negative(self):
        self.assertEqual(self.b142["loans"][1]["rows"]["balance"][1],
                         Decimal("-1497.35"))


class TestMoneyRecognizer(unittest.TestCase):
    """Each case below returned a plausible wrong number before its guard."""

    def money(self, text, want_last=True, sense=""):
        got = _money_in(text, want_last, sense)
        return None if got is None else got[0]

    def test_a_trailing_minus_survives_rightmost_wins(self):
        # In "$6,000.25-" the specific pattern matches at column 0 and the
        # generic one matches "6,000.25" one column FURTHER RIGHT, so a naive
        # rightmost-wins picks the generic reading and silently drops the
        # sign, turning -6000.25 into 6000.25. Overlap rejection is the fix.
        self.assertEqual(self.money("   $6,000.25-"), Decimal("-6000.25"))

    def test_continental_grouping_is_not_read_as_a_prefix(self):
        # Measured before the boundary check existed:
        #   1.234,56      -> 1.23   a THOUSANDFOLD error
        #   12.345.678,90 -> 12.34  a MILLIONFOLD one
        self.assertEqual(self.money("1.234,56"), Decimal("1234.56"))
        self.assertEqual(self.money("12.345.678,90"), Decimal("12345678.90"))
        self.assertEqual(self.money("1.234,56-"), Decimal("-1234.56"))

    def test_an_infix_of_a_longer_number_is_refused(self):
        # 1,234.567 -> 1234.56, a third decimal silently dropped.
        self.assertIsNone(self.money("1,234.567"))

    def test_ordinary_punctuation_still_works(self):
        # The test is adjacency through AT MOST ONE separator. A full stop
        # ending a sentence is not a third decimal place, and refusing it
        # would trade one wrong answer for a different one.
        self.assertEqual(self.money("Ending Cash 1,234.56."), Decimal("1234.56"))

    def test_a_single_separator_is_refused_rather_than_guessed(self):
        # 1.234 is one thousand two hundred thirty-four continental and
        # one-point-two-three-four decimal. Reading either would be choosing a
        # convention the token does not state.
        self.assertIsNone(self.money("1.234"))
        self.assertIsNone(self.money("123,45"))

    def test_notational_negatives(self):
        for text in ("<$1,234.56>", "(1,234.56)", "-$1,234.56", "$-1,234.56",
                     "1,234.56-"):
            self.assertEqual(self.money(text), Decimal("-1234.56"), text)

    def test_dr_cr_takes_its_sign_from_the_declared_convention(self):
        # ledger is the trial-balance reading and the default; statement is
        # the customer-facing one, where a credit INCREASES the balance. Which
        # a report uses is not visible in the token, and reading a customer
        # statement through the ledger default inverts every signed amount.
        self.assertEqual(self.money("1,234.56 CR"), Decimal("-1234.56"))
        self.assertEqual(self.money("1,234.56 DR"), Decimal("1234.56"))
        self.assertEqual(self.money("1,234.56 CR", sense="statement"),
                         Decimal("1234.56"))
        self.assertEqual(self.money("1,234.56 DR", sense="statement"),
                         Decimal("-1234.56"))

    def test_inner_padding_is_part_of_one_value(self):
        self.assertEqual(self.money("$          6,045.75"), Decimal("6045.75"))

    def test_malformed_is_none_not_zero(self):
        self.assertIsNone(self.money("$8,0000"))

    def test_first_and_last(self):
        line = "  1.00   and   2.00"
        self.assertEqual(self.money(line, want_last=False), Decimal("1.00"))
        self.assertEqual(self.money(line, want_last=True), Decimal("2.00"))


class TestIntegerAndDecimal(unittest.TestCase):
    def test_a_grouped_integer_is_unambiguous(self):
        # An integer has no decimal part, so 1,234 and 1.234 are both 1234
        # whatever convention the report uses -- which is why this admits a
        # separator the money core refuses to guess at.
        self.assertEqual(_integer_in("1,234", False)[0], 1234)
        self.assertEqual(_integer_in("1.234", False)[0], 1234)

    def test_an_integer_does_not_truncate_a_decimal(self):
        # 1.23 used to answer 1, which is a value the caller did not ask for
        # and cannot tell from a real one. A count of 1,234 reading as 1 is
        # the same silent, plausible, catastrophic shape.
        self.assertIsNone(_integer_in("1.23", False))
        self.assertIsNone(_integer_in("1,234.56", False))

    def test_a_mixture_of_separators_is_not_one_integer(self):
        self.assertIsNone(_integer_in("1,234.567", False))

    def test_as_integer_delimits_the_span(self):
        # `right of "Teller #:"` yields "386     Summary"; `as integer`
        # reduces it to 386 by taking the integer-shaped token out.
        self.assertEqual(_integer_in("386                    Summary", False)[0], 386)

    def test_decimal_keeps_any_number_of_places(self):
        self.assertEqual(_decimal_in("1,234.5678", False)[0], Decimal("1234.5678"))
        self.assertEqual(_decimal_in("42", False)[0], Decimal("42"))


class TestDateRecognizer(unittest.TestCase):
    def test_iso_and_named_months(self):
        self.assertEqual(_date_in("2026-03-15", "")["val"], date(2026, 3, 15))
        self.assertEqual(_date_in("15-Mar-2026", "")["val"], date(2026, 3, 15))
        self.assertEqual(_date_in("Mar 15 2026", "")["val"], date(2026, 3, 15))

    def test_the_token_settles_it_where_it_can(self):
        self.assertEqual(_date_in("27/12/2026", "")["val"], date(2026, 12, 27))

    def test_and_refuses_where_it_cannot(self):
        got = _date_in("03/04/2026", "")
        self.assertIsNone(got["val"])
        self.assertEqual(got["why"], "ambiguous-date")

    def test_a_declaration_is_authoritative_not_a_hint(self):
        self.assertEqual(_date_in("03/04/2026", "dmy")["val"], date(2026, 4, 3))
        self.assertEqual(_date_in("03/04/2026", "mdy")["val"], date(2026, 3, 4))
        # Under mdy, 27/12/2026 is invalid -- month 27 does not exist, and the
        # author has stated this column is month-first. Silently re-reading it
        # day-first would be guessing against an explicit declaration.
        got = _date_in("27/12/2026", "mdy")
        self.assertIsNone(got["val"])
        self.assertEqual(got["why"], "invalid-date")


class TestCustomTypes(unittest.TestCase):
    SPEC = r'''
type usd_bracketed:
    /<\$?([\d,]+\.\d{2})>/   -> negate as decimal
    /\$?\s*([\d,]+\.\d{2})/  -> as decimal
    output: money

type euro_date:
    /[0-9]{2}\/[0-9]{2}\/[0-9]{4}/ -> dmy
    output: date

type rewritten_date:
    /([0-9]{2})\/([0-9]{2})\/([0-9]{4})/$3-$2-$1/ -> as date
    output: date

section report:
    field a: right of "A:" as usd_bracketed
    field b: right of "B:" as usd_bracketed
    field c: right of "C:" as euro_date
    field d: right of "D:" as rewritten_date
    field e: right of "E:" as usd_bracketed
'''

    def test_rules_are_tried_in_order(self):
        r = arispec.parse("A: <$1,234.56>\nB: $1,234.56\nC: 03/04/2026\n"
                          "D: 03/04/2026\nE: nothing here\n", self.SPEC)
        self.assertTrue(r.ok, r.message)
        # The negative form must be declared before the general one, or the
        # general one matches its digits and drops the sign.
        self.assertEqual(r.value["a"], Decimal("-1234.56"))
        self.assertEqual(r.value["b"], Decimal("1234.56"))

    def test_a_dialect_and_a_transform_agree(self):
        # The same conversion by two mechanisms: naming a dialect, and a
        # /re/repl/ rewrite to ISO with $-group references before the date
        # conversion sees it. If they disagreed, one of them would be wrong.
        r = arispec.parse("A: 1.00\nB: 1.00\nC: 03/04/2026\nD: 03/04/2026\n"
                          "E: 1.00\n", self.SPEC)
        self.assertEqual(r.value["c"], date(2026, 4, 3))
        self.assertEqual(r.value["d"], date(2026, 4, 3))

    def test_a_value_matching_no_rule_is_unknown_for_that_cell_alone(self):
        r = arispec.parse("A: <$1.00>\nB: 2.00\nC: 03/04/2026\nD: 03/04/2026\n"
                          "E: nothing here\n", self.SPEC)
        self.assertIs(r.value["e"], UNKNOWN)
        self.assertEqual(r.value["b"], Decimal("2.00"))
        self.assertIn("no-rule-matched", {d["reason"] for d in r.diagnostics})

    def test_an_escaped_slash_in_a_rule_is_not_a_delimiter(self):
        # A date pattern always contains escaped slashes, and a regex-based
        # split cannot tell one from a delimiter. Upstream this silently
        # mis-split the rule into a transform whose pattern ended in a lone
        # backslash, which the engine then rejected.
        from arispec._spec import split_rule
        parts, action = split_rule(r"/[0-9]{2}\/[0-9]{2}\/[0-9]{4}/ -> dmy")
        self.assertEqual(parts, [r"[0-9]{2}\/[0-9]{2}\/[0-9]{4}"])
        self.assertEqual(action, "dmy")
        parts, action = split_rule(r"/([0-9]{2})\/([0-9]{2})/$2-$1/ -> as date")
        self.assertEqual(parts, [r"([0-9]{2})\/([0-9]{2})", "$2-$1"])
        self.assertEqual(action, "as date")


class TestUsing(unittest.TestCase):
    def test_a_binding_applies_to_nested_sections(self):
        spec = r'''
section report:
    using date: dmy
    section rows repeats starts(/^ROW /):
        field posted: first date as date
'''
        r = arispec.parse("ROW 03/04/2026\nROW 05/06/2026\n", spec)
        self.assertEqual([x["posted"] for x in r.value["rows"]],
                         [date(2026, 4, 3), date(2026, 6, 5)])

    def test_an_inner_binding_overrides_an_outer(self):
        spec = r'''
section report:
    using date: dmy
    section inner starts(/^ROW /):
        using date: mdy
        field posted: first date as date
'''
        r = arispec.parse("ROW 03/04/2026\n", spec)
        self.assertEqual(r.value["inner"]["posted"], date(2026, 3, 4))

    def test_an_unknown_binding_is_refused_when_the_spec_is_read(self):
        # It used to fall through silently and hand the field back the raw
        # line as text -- and inspect's own hint for an ambiguous date told
        # authors to write exactly the binding that did it. The remedy for one
        # silent wrong answer was itself a silent wrong answer.
        spec = "section report:\n    using date: german\n    field a: right of \"A:\"\n"
        r = arispec.parse("A: x\n", spec)
        self.assertFalse(r.ok)
        self.assertIn("names neither a declared type nor a dialect", r.message)
        self.assertIn("dmy", r.message)         # the refusal names what IS accepted

    def test_a_using_outside_a_section_is_refused(self):
        r = arispec.parse("A: x\n", "using date: dmy\nsection report:\n    field a: right of \"A:\"\n")
        self.assertFalse(r.ok)
        self.assertIn("must be written inside a section", r.message)


class TestTrace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = arispec.trace(fixture("teller_totals.rpt"), TELLER_SPEC)

    def test_it_describes_the_run_that_happened(self):
        self.assertTrue(self.t.result.ok)
        self.assertEqual(self.t.result.value["branch"], 14)

    def test_an_anchor_is_a_claim(self):
        # A literal the spec names is the most spec-relevant text on the page.
        # Left out, it would sit in the unclaimed list and depress coverage by
        # exactly the literals the author wrote.
        kinds = {c["kind"] for c in self.t.claims}
        self.assertEqual(kinds, {"field", "anchor", "section"})
        anchors = [c["text"] for c in self.t.claims if c["kind"] == "anchor"]
        self.assertIn("Beginning Cash", anchors)

    def test_blanks_are_not_content(self):
        # A print image is largely column padding; counting it would put every
        # specification near 1.0, which is the flattering-and-useless way to
        # be wrong.
        self.assertGreater(self.t.content_chars, 0)
        self.assertLess(self.t.content_chars,
                        sum(len(l) for l in fixture("teller_totals.rpt").split("\n")))
        self.assertTrue(all(u["text"].strip() for u in self.t.unclaimed))

    def test_unclaimed_finds_what_the_spec_does_not_read(self):
        texts = " ".join(u["text"] for u in self.t.unclaimed)
        self.assertIn("Fifties", texts)         # a field this spec never declared

    def test_a_structural_overlap_is_not_a_collision(self):
        # `section report starts(/^Branch: /)` beside `field branch: right of
        # "Branch:"` names the same characters ON PURPOSE. Counting that made
        # correct headings the entire reported rate on a spec with nothing
        # wrong with it -- a number that fires on the commonest correct shape
        # in the language is noise with a name.
        self.assertEqual(self.t.collisions, ())
        self.assertEqual(self.t.collision_rate, 0.0)

    def test_the_fractions_carry_their_own_definition(self):
        self.assertIn("Not a grade", self.t.content_coverage_is)
        self.assertIn("value on at least one side", self.t.collision_rate_is)


class TestResultAndUnknown(unittest.TestCase):
    def test_a_result_has_no_truth_value(self):
        # A parse that succeeded with unreadable cells is not a failure.
        r = arispec.parse("A: 1\n", 'section report:\n    field a: right of "A:"\n')
        with self.assertRaises(TypeError):
            bool(r)

    def test_unknown_has_no_truth_value(self):
        with self.assertRaises(TypeError):
            bool(UNKNOWN)
        self.assertIs(UNKNOWN, type(UNKNOWN)())

    def test_ok_is_about_the_spec_not_the_report(self):
        # A spec that cannot be read is ok=False; a report with unreadable
        # cells parses fine and records them. Collapsing the two would make a
        # malformed cell look like a broken spec.
        r = arispec.parse("A: not money\n",
                          'section report:\n    field a: right of "A:" as money\n')
        self.assertTrue(r.ok)
        self.assertIs(r.value["a"], UNKNOWN)
        self.assertEqual(r.diagnostics[0]["reason"], "malformed-money")

    def test_the_public_tables_are_derivable(self):
        self.assertIn("money", arispec.builtin_types())
        self.assertEqual(arispec.type_dialects()["date"], ("dmy", "mdy"))
        self.assertTrue(arispec.money_patterns())
        self.assertTrue(arispec.date_patterns())


if __name__ == "__main__":
    unittest.main()
