# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""ARI -- anchor-relative identification.

Declarative extraction of fields from irregular, semi-structured text: legacy
print reports, mainframe spool, teller totals, and the 2D grids that arrive as
spreadsheets.

**Why not a column, and why not a heading.** Measured on two real teller
reports: the ``Amount`` heading ends at column 74 while its own values end at
78, 78 and **79**. The heading is adrift of its data by four columns in one
file and eleven in the other, because headings and data drift apart over
decades of separate edits. And the row that runs a column further is the
negative one -- ``$6,000.25-`` -- because a trailing minus is appended *after*
right-justification, so negatives are one column wider than the positives
above them. Pin that column to 78 and you truncate the sign; pin it to 79 and
every positive carries a leading space.

Neither the heading nor the column can find the amount. What works is
**bounding by type**: *the last money-shaped token on this row*. So ``as
<type>`` does not merely convert a value, it **delimits** it -- and that is
the central idea of the language.

    import arispec

    spec = '''
    page:
        break: formfeed
        drop: 2

    section report:
        section tellers repeats starts(/^Teller: /):
            field name:       between "Teller:" and "Teller #:"
            field teller_no:  right of "Teller #:" as integer
            field beginning:  right of "Beginning Cash" as money

            section detail starts(/^GL\\s+Tran #/) ends(/^\\s*$/):
                rows:
                    field gl:     columns 0-24
                    field amount: last money
    '''

    r = arispec.parse(report_text, spec)
    if r.ok:
        for t in r.value["tellers"]:
            print(t["teller_no"], t["beginning"])

Fields are anchored by **label**, not by row offset, and that is the case that
matters: in the fixture, teller 386 prints Beginning/Ending/Total while
tellers 261 and 262 print Beginning/Total/Ending. An offset-based read returns
the wrong number for two of the three and reports nothing wrong.

A ``rows:`` block emits a **frame** -- columns of equal length, which
``polars.DataFrame`` and ``pandas.DataFrame`` both take directly, with no
dependency on either from here. arispec depends on nothing at all.

A cell that matches no rule becomes :data:`UNKNOWN` for that cell alone --
never a silent zero, never a raise that sinks the import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._engine import Ctx, build_grid, build_record, find_instances
from ._recognize import (BUILTIN_TYPES, TYPE_DIALECTS, date_patterns,
                         money_patterns)
from ._spec import Section, SpecError, parse_spec
from ._trace import collisions as _collisions, coverage as _coverage
from ._unknown import UNKNOWN

__version__ = "0.1.0"

__all__ = [
    "UNKNOWN", "Result", "SpecError", "builtin_types", "clean_grid",
    "date_patterns", "inspect", "money_patterns", "parse", "parse_spec",
    "trace", "Trace", "type_dialects",
]


@dataclass(frozen=True, slots=True)
class Trace:
    """Everything :func:`parse` returns, plus an account of the spec against
    the report's own bytes."""

    result: "Result"
    claims: tuple = ()
    unclaimed: tuple = ()
    content_chars: int = 0
    claimed_chars: int = 0
    content_coverage: float | None = None
    collisions: tuple = ()
    collision_rate: float | None = None
    content_coverage_is: str = (
        "claimed non-blank characters / non-blank characters on the lines the "
        "page: directive KEPT. Not a grade: a report carrying commentary, "
        "totals the spec does not read, or rule lines can never reach 1.0 and "
        "should not. Useful as a DIFFERENCE -- between two candidate specs "
        "over one corpus, or one spec before and after a field is added. Two "
        "specs are comparable only when they strip the same furniture.")
    collision_rate_is: str = (
        "fields whose claim overlaps another path's / fields that produced a "
        "value. A collision needs a value on at least one side, because a "
        "section heading and a field reading the same label name the same "
        "characters on purpose.")


@dataclass(frozen=True, slots=True)
class Result:
    """What a parse produced, and what it could not read.

    ``ok`` is about the *specification*, not about the report: a spec that
    cannot be read gives ``ok=False`` and a ``message``, while a report with
    unreadable cells parses fine and records them in ``diagnostics``. The two
    are different failures and collapsing them would make a malformed cell
    look like a broken spec.
    """

    ok: bool
    value: Any = None
    message: str = ""
    diagnostics: tuple = ()

    def __bool__(self):
        raise TypeError(
            "a Result has no truth value -- a parse that succeeded with "
            "unreadable cells is not a failure. Test it with '.ok'.")


def builtin_types() -> tuple:
    """The base types every spec may name."""
    return BUILTIN_TYPES


def type_dialects() -> dict:
    """The dialect words a ``using`` may name, per builtin type.

    Public so a refusal can *derive* the list of what is accepted rather than
    restate it -- or the message and the code drift, and the message is what
    an author believes.
    """
    return {k: tuple(v) for k, v in TYPE_DIALECTS.items()}


def clean_grid(report_text: str, spec_text: str) -> list:
    """The report with its page furniture stripped.

    Everything downstream reads this, so ``up``/``down`` count over the clean
    grid and never over the physical file -- an offset means the same thing
    regardless of where a page happened to break.
    """
    spec = parse_spec(spec_text)
    return [g.text for g in build_grid(report_text, spec.page)]


def parse(report_text: str, spec_text: str) -> Result:
    """Run *spec_text* against *report_text*."""
    try:
        spec = parse_spec(spec_text)
    except SpecError as e:
        return Result(ok=False, message=str(e))

    grid = build_grid(report_text, spec.page)
    ctx = Ctx(types=spec.types, usings={}, trace=False)
    value, diags = _walk(grid, spec.root, ctx)
    return Result(ok=True, value=value, diagnostics=tuple(diags))


def inspect(report_text: str, spec_text: str) -> Result:
    """:func:`parse`, and read its ``diagnostics``.

    Every cell the recognizers could not read, with the path that names it,
    the reason, and the physical line. ``ambiguous-date`` and
    ``malformed-money`` are the two worth watching: the first means the report
    genuinely does not say, and the second that it said something unexpected.
    """
    return parse(report_text, spec_text)


def trace(report_text: str, spec_text: str) -> Trace:
    """:func:`parse`, plus what the specification did and did not explain.

        t = arispec.trace(report, spec)
        for u in t.unclaimed:
            print(u["line"], u["text"])     # what the spec does not account for

    ``trace`` and ``parse`` share one walk, so a trace cannot describe a
    different program from the one that ran.

    The useful direction is ``unclaimed``: a spec that quietly stopped
    matching shows up as text nothing explained, where a coverage number alone
    would only drift.
    """
    try:
        spec = parse_spec(spec_text)
    except SpecError as e:
        return Trace(result=Result(ok=False, message=str(e)))

    grid = build_grid(report_text, spec.page)
    ctx = Ctx(types=spec.types, usings={}, trace=True)
    spans = find_instances(grid, 0, len(grid), spec.root)
    if not spans:
        return Trace(result=Result(ok=True, value={}, diagnostics=(
            {"path": spec.root.name or "<root>", "reason": "section-not-found",
             "line": 0},)))
    lo, hi = spans[0]
    rec, diags, claims = build_record(grid, lo, hi, spec.root, ctx,
                                      spec.root.name or "")
    cov = _coverage(grid, claims)
    col = _collisions(claims)
    return Trace(
        result=Result(ok=True, value=rec, diagnostics=tuple(diags)),
        claims=tuple(claims),
        unclaimed=tuple(cov["unclaimed"]),
        content_chars=cov["content_chars"],
        claimed_chars=cov["claimed_chars"],
        content_coverage=cov["fraction"],
        collisions=tuple(col["collisions"]),
        collision_rate=col["rate"],
    )


def _walk(grid, root: Section, ctx: Ctx):
    spans = find_instances(grid, 0, len(grid), root)
    if not spans:
        return {}, [{"path": root.name or "<root>",
                     "reason": "section-not-found", "line": 0}]
    lo, hi = spans[0]
    rec, diags, _claims = build_record(grid, lo, hi, root, ctx, root.name or "")
    return rec, diags
