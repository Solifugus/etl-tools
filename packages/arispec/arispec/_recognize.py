# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Type recognizers: one recognizer per type, covering the UNION of forms.

A single report disagrees with itself between sections -- three branches of
one teller report print money three different ways -- so a type is a
*permissive recognizer* over the union rather than a fixed pattern. The
precedent is date parsing: many forms arrive and most can be deciphered
without being told which.

**`as <type>` delimits as well as converts.** The span handed in carries
neighbouring text; the recognizer takes the token of that shape out of it.
That is the locator that survives a heading four columns adrift of its own
data and a negative one column wider than the positive above it, and it is
the central idea of the language.

Ported from gBASIC's ``stdlib/ari.bas``. The guards below are not defensive
programming -- each one is a measured defect, recorded where it was fixed.
"""

from __future__ import annotations

import re
from datetime import date as _date
from decimal import Decimal, InvalidOperation


__all__ = ["BUILTIN_TYPES", "TYPE_DIALECTS", "convert", "date_patterns",
           "money_patterns"]

BUILTIN_TYPES = ("date", "money", "integer", "decimal", "text")

#: The dialect words a ``using`` may name, per builtin. Public for the same
#: reason the pattern tables are: a refusal that lists what IS accepted has to
#: derive the list rather than restate it, or the message and the code drift
#: and the message is what an author believes.
TYPE_DIALECTS = {"date": ("dmy", "mdy"), "money": ("ledger", "statement")}

# ------------------------------------------------------------------ money

#: THE NUMERIC CORE, shared by every money pattern.
#:
#: Two alternatives::
#:
#:     [0-9]{1,3}(\.[0-9]{3})+,[0-9]{2}    1.234,56   12.345.678,90
#:     [0-9,]+\.[0-9]{2}                   1,234.56   1234.56
#:
#: What makes this decidable without a declaration: each convention uses THE
#: OTHER CHARACTER for grouping, so where both appear the LAST one is the
#: decimal mark. That is a fact about the two notations, not a guess about
#: this report.
#:
#: What is deliberately NOT admitted is a single separator. ``1.234`` is one
#: thousand two hundred thirty-four continental and one-point-two-three-four
#: decimal; reading either would be choosing a convention the token does not
#: state. It stays malformed.
#:
#: The continental alternative is written FIRST and that ordering is
#: load-bearing here in a way it is not upstream. POSIX ERE is leftmost-
#: LONGEST, so gBASIC gets the grouped form regardless of order; Python's
#: ``re`` is leftmost-FIRST and would take whichever alternative is written
#: first. Same answer, for a different reason -- worth knowing before anyone
#: tidies the alternation.
_NUM_CORE = r"([0-9]{1,3}(\.[0-9]{3})+,[0-9]{2}|[0-9,]+\.[0-9]{2})"

#: Ordered MOST-SPECIFIC FIRST: the bracket, paren, CR and trailing-minus
#: forms must be tried before the plain one, or the plain pattern matches
#: their digits and drops the sign.
_MONEY = [
    (r"<[ ]*\$?[ ]*" + _NUM_CORE + r"[ ]*>", True, ""),
    (r"\([ ]*\$?[ ]*" + _NUM_CORE + r"[ ]*\)", True, ""),
    (r"\$?[ ]*" + _NUM_CORE + r"[ ]*CR", True, "credit"),
    (r"\$?[ ]*" + _NUM_CORE + r"[ ]*DR", False, "debit"),
    (r"\$?[ ]*" + _NUM_CORE + r"[ ]*-", True, ""),
    (r"-[ ]*\$[ ]*" + _NUM_CORE, True, ""),
    (r"\$[ ]*-[ ]*" + _NUM_CORE, True, ""),
    (r"-[ ]*" + _NUM_CORE, True, ""),
    (r"\$[ ]*" + _NUM_CORE, False, ""),
    (_NUM_CORE, False, ""),
]


def money_patterns():
    """The recognizer table, public so discovery and parsing share one copy.

    Two copies of "what money looks like" drift, and a profile that reports a
    money column the engine cannot read produces a spec that is wrong before
    it is executed. One table, two jobs: this answers with the *one* span it
    decided on, where discovery has to see every candidate.
    """
    return [{"re": r, "neg": n, "sense": s} for r, n, s in _MONEY]


def _to_amount(digits: str, negate: bool) -> Decimal | None:
    """Strip grouping separators and convert. ``None`` when malformed.

    THE LAST SEPARATOR IS THE DECIMAL MARK and everything before it is
    grouping. One rule reads both conventions without being told which,
    because each uses the other character to group.
    """
    last_dot = digits.rfind(".")
    last_comma = digits.rfind(",")
    if last_comma > last_dot:
        clean = digits.replace(".", "").replace(",", ".")
    else:
        clean = digits.replace(",", "")
    try:
        value = Decimal(clean)
    except InvalidOperation:
        # Reachable from the CUSTOM TYPE path, where the digits are whatever
        # the author's own regex captured. Upstream this took the whole parse
        # down until it was measured; here it is one unknown cell.
        return None
    return -value if negate else value


def _digit_at(text: str, i: int) -> bool:
    return 0 <= i < len(text) and text[i].isdigit()


def _digits_begin(text: str, a: int, b: int) -> int:
    for i in range(a, b):
        if _digit_at(text, i):
            return i
    return a


def _inside_longer_number(text: str, a: int, b: int) -> bool:
    """Does the match at [a, b) sit INSIDE a longer numeric token?

    Every money pattern ends in ``\\.[0-9]{2}`` and none of them requires the
    match to be the WHOLE number, so without this a pattern matches an infix
    and returns it as the value. Measured before the check existed::

        1,234.567      -> 1234.56     a third decimal silently dropped
        1.234,56       -> 1.23        a THOUSANDFOLD error
        12.345.678,90  -> 12.34       a MILLIONFOLD one
        1.234,56-      -> 1.23        and the sign lost with it

    Not one of them raised, and each returns a number a reader would accept.

    THE TEST IS ADJACENCY THROUGH AT MOST ONE SEPARATOR, not merely adjacency.
    A digit touching the match means the token continues; a ``.`` or ``,``
    means it continues only if a digit follows. That distinction keeps
    ordinary punctuation working -- ``Ending Cash 1,234.56.`` ends a sentence,
    and refusing it would trade one wrong answer for a different one.
    """
    if _digit_at(text, a - 1):
        return True
    if a - 1 >= 0 and text[a - 1] in ".," and _digit_at(text, a - 2):
        return True
    if _digit_at(text, b):
        return True
    if b < len(text) and text[b] in ".," and _digit_at(text, b + 1):
        return True
    return False


def _money_in(text: str, want_last: bool, sense: str):
    """Scan *text* for a money value. Returns ``(value, at, length)`` or None.

    Spans are claimed MOST-SPECIFIC-PATTERN FIRST, and any later match that
    overlaps one already claimed is rejected. That is what makes a trailing
    minus survive: in ``...  $6,000.25-`` the specific pattern matches
    ``$6,000.25-`` at column 69 and the generic one matches ``6,000.25`` at
    column 70 -- further RIGHT, so a naive "rightmost wins" picks the generic
    reading and silently drops the sign, turning -6000.25 into 6000.25.
    """
    chosen = []
    for pat, neg, psense in _MONEY:
        for m in re.finditer(pat, text):
            a1, b1 = m.start(), m.end()
            if any(a1 < c[1] and c[0] < b1 for c in chosen):
                continue
            core = m.group(1)
            nb = _digits_begin(text, a1, b1)
            if _inside_longer_number(text, nb, nb + len(core)):
                continue
            # A DR/CR-suffixed amount takes its sign from the declared
            # convention rather than from the pattern's own default, which is
            # the ledger one. A customer statement read through the ledger
            # default has every signed amount inverted, with nothing raised.
            negate = neg
            if sense == "statement":
                if psense == "credit":
                    negate = False
                elif psense == "debit":
                    negate = True
            value = _to_amount(core, negate)
            if value is not None:
                chosen.append((a1, b1, value))
    if not chosen:
        return None
    best = max(chosen, key=lambda c: c[0]) if want_last else min(chosen, key=lambda c: c[0])
    return best[2], best[0], best[1] - best[0]


# --------------------------------------------------- integer and decimal

def _whole_match(text: str, matches, want_last: bool):
    """The first or last match that is a WHOLE token, not an infix.

    The same defect as the money one, one level over, and no entry in the
    register had probed it because every entry was written about ``as
    money``. Measured::

        1,234      as integer -> 1     as decimal -> 1
        1,234.56   as integer -> 1
        1.234,56   as decimal -> 1.234

    A count of 1,234 reading as 1 is the same silent, plausible, catastrophic
    shape -- and ``as integer`` is the commonest conversion in a generated
    spec, because it is what a section's own number is read with.
    """
    keep = [m for m in matches
            if not _inside_longer_number(text, m.start(), m.end())]
    if not keep:
        return None
    return keep[-1] if want_last else keep[0]


#: ONE SEPARATOR KIND THROUGHOUT. Written as ``[.,]`` inside the group it
#: accepts a MIXTURE, and ``1,234.567`` then matched entirely -- ``.567`` read
#: as a third group -- and came back as the integer 1234567.
#:
#: A GROUPED INTEGER IS UNAMBIGUOUS in a way a grouped decimal is not: an
#: integer has no decimal part, so ``1,234`` and ``1.234`` are both 1234
#: whatever convention the report uses. That is why this admits a separator
#: the money core refuses to guess at.
_INTEGER = r"-?[0-9]{1,3}(,[0-9]{3})+|-?[0-9]{1,3}(\.[0-9]{3})+|-?[0-9]+"
_DECIMAL = r"-?[0-9]{1,3}(\.[0-9]{3})+,[0-9]+|-?[0-9,]+\.[0-9]+"


def _integer_in(text: str, want_last: bool):
    m = _whole_match(text, re.finditer(_INTEGER, text), want_last)
    if m is None:
        return None
    body = m.group(0).replace(",", "").replace(".", "")
    return int(body), m.start(), m.end() - m.start()


def _decimal_in(text: str, want_last: bool):
    m = _whole_match(text, re.finditer(_DECIMAL, text), want_last)
    if m is None:
        # A token with no decimal part is still a decimal value. gBASIC has
        # one number type so the fallback is invisible there; here it is
        # widened so `as decimal` always answers with a Decimal.
        iv = _integer_in(text, want_last)
        return None if iv is None else (Decimal(iv[0]), iv[1], iv[2])
    body = m.group(0)
    neg = body.startswith("-")
    value = _to_amount(body[1:] if neg else body, neg)
    if value is None:
        return None
    return value, m.start(), m.end() - m.start()


# ------------------------------------------------------------------- date

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
           "jul", "aug", "sep", "oct", "nov", "dec")

_DATES = [
    (r"([0-9]{4})-([0-9]{2})-([0-9]{2})", "iso", False),
    (r"([0-9]{1,2})[-/. ]([A-Za-z]{3})[-/. ]([0-9]{4})", "dmy_name", False),
    (r"([A-Za-z]{3})[-/. ]([0-9]{1,2})[-/. ]([0-9]{4})", "mdy_name", False),
    (r"([0-9]{1,2})[/.-]([0-9]{1,2})[/.-]([0-9]{4})", "numeric", True),
]


def date_patterns():
    """The date recognizer table, public for the same reason as money's."""
    return [{"re": r, "kind": k, "needs_dialect": d} for r, k, d in _DATES]


def _month_no(abbr: str) -> int:
    try:
        return _MONTHS.index(abbr[:3].lower()) + 1
    except ValueError:
        return 0


def _mk(y, mo, da, start, length):
    try:
        return {"val": _date(int(y), int(mo), int(da)), "why": "",
                "at": start, "length": length}
    except ValueError:
        return {"val": None, "why": "invalid-date", "at": start, "length": length}


def _date_in(text: str, dialect: str):
    for pat, kind, _needs in _DATES:
        m = re.search(pat, text)
        if m is None:
            continue
        g, at, ln = m.groups(), m.start(), m.end() - m.start()
        if kind == "iso":
            return _mk(g[0], g[1], g[2], at, ln)
        if kind in ("dmy_name", "mdy_name"):
            name, day = (g[1], g[0]) if kind == "dmy_name" else (g[0], g[1])
            mo = _month_no(name)
            if mo == 0:
                return {"val": None, "why": "unknown-month-name", "at": at, "length": ln}
            return _mk(g[2], mo, day, at, ln)

        # numeric: the only form that may need a declared dialect.
        a, b, y = int(g[0]), int(g[1]), g[2]
        if dialect == "dmy":
            return _mk(y, b, a, at, ln)
        if dialect == "mdy":
            # A DECLARATION IS AUTHORITATIVE, NOT A HINT. Under `using date:
            # mdy`, 27/12/2026 is invalid -- month 27 does not exist, and the
            # author has stated this column is month-first. Silently re-reading
            # it day-first would be guessing against an explicit declaration.
            return _mk(y, a, b, at, ln)
        if a > 12:
            return _mk(y, b, a, at, ln)
        if b > 12:
            return _mk(y, a, b, at, ln)
        # Nothing in 03/04/2026 says which of 3 April and 4 March it is, and
        # picking the commoner one would be wrong half the time in silence.
        return {"val": None, "why": "ambiguous-date", "at": at, "length": ln}
    return {"val": None, "why": "no-date-found", "at": 0, "length": 0}


# ---------------------------------------------------------------- convert

def _trim_extent(span: str):
    """The extent of a span's trimmed content.

    ``strip`` begins at the first non-blank character, so the first occurrence
    of the trimmed text in the span IS the offset -- no second scanner, and no
    rule to drift.
    """
    t = span.strip()
    if not t:
        return 0, 0
    return span.find(t), len(t)


def _as_text(span: str):
    at, ln = _trim_extent(span)
    return {"val": span.strip(), "why": "", "at": at, "length": ln}


def convert(span: str, ty: str, want_last: bool, ctx) -> dict:
    """Convert an extracted span according to its declared type.

    *ctx* carries the spec's custom ``type`` declarations and the ``using``
    bindings in scope, so a section can rebind what ``money`` or ``date``
    means for itself and its children.
    """
    if ty in ("", "text"):
        return _as_text(span)

    # A `using <builtin>: <name>` binding in scope either names a DIALECT of
    # that builtin or redirects it to a custom type; a field naming a custom
    # type directly beats any binding.
    eff, dialect = ty, ""
    bound = ctx.usings.get(ty)
    if bound is not None:
        if bound in TYPE_DIALECTS.get(ty, ()):
            dialect = bound
        else:
            eff = bound

    custom = ctx.types.get(eff)
    if custom is not None:
        return _convert_custom(span, custom)

    if eff == "money":
        got = _money_in(span, want_last, dialect)
        if got is None:
            return {"val": None, "why": "malformed-money", "at": 0, "length": 0}
        return {"val": got[0], "why": "", "at": got[1], "length": got[2]}
    if eff == "integer":
        got = _integer_in(span, want_last)
        if got is None:
            return {"val": None, "why": "no-integer-found", "at": 0, "length": 0}
        return {"val": got[0], "why": "", "at": got[1], "length": got[2]}
    if eff == "decimal":
        got = _decimal_in(span, want_last)
        if got is None:
            return {"val": None, "why": "no-decimal-found", "at": 0, "length": 0}
        return {"val": got[0], "why": "", "at": got[1], "length": got[2]}
    if eff == "date":
        return _date_in(span, dialect)
    return _as_text(span)


def _py_replacement(repl: str) -> str:
    """Translate a spec's ``$1``..``$9`` group references to Python's.

    The SPEC LANGUAGE is the user-facing surface and one spec file has to read
    the same in both trees, so ``$N`` stays what an author writes and the
    translation happens here. gBASIC's ``replace()`` takes ``$N``; Python's
    ``re.sub`` takes ``\\N``, and would silently emit a literal ``$3-$2-$1``
    if handed the spec's own spelling -- a date that becomes the string
    "$3-$2-$1" and then fails to be a date, which reads as a bad fixture
    rather than a bad translation.
    """
    out, i = [], 0
    while i < len(repl):
        c = repl[i]
        if c == "\\":
            out.append("\\\\")
            i += 1
        elif c == "$" and i + 1 < len(repl) and repl[i + 1].isdigit():
            out.append(f"\\g<{repl[i + 1]}>")
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _convert_custom(span: str, custom) -> dict:
    """A custom type is an ordered rule list; the first match wins.

    So the negative form must be declared before the general one, which is why
    every money type in the worked specs opens with its bracket or
    trailing-minus rule.
    """
    for rule in custom.rules:
        m = re.search(rule.pattern, span)
        if m is None:
            continue
        # A rule need not capture: with no group, the whole match is the
        # value. With a TRANSFORM the whole match is the input to the rewrite
        # and group references live in the replacement -- feeding it only the
        # first capture would hand a date rule its two-digit day and rewrite
        # that.
        raw = m.group(0)
        if not rule.replacement and m.groups() and m.group(1) is not None:
            raw = m.group(1)
        if rule.replacement:
            raw = re.sub(rule.pattern, _py_replacement(rule.replacement), raw)

        # The claimed span is the RULE's match against the span, never the
        # rewrite's own offsets: with a transform in play `raw` is a string
        # that does not exist in the source, so a position inside it points at
        # nothing a reader could find.
        at, ln = m.start(), m.end() - m.start()
        if custom.base == "date":
            dr = _date_in(raw, rule.dialect)
            if dr["val"] is None:
                return dr
            return {"val": dr["val"], "why": "", "at": at, "length": ln}
        value = _to_amount(raw, rule.negate)
        if value is not None:
            return {"val": value, "why": "", "at": at, "length": ln}
    # A value matching no rule becomes unknown for that cell alone -- never a
    # silent zero, and never a raise that sinks the import.
    return {"val": None, "why": "no-rule-matched", "at": 0, "length": 0}
