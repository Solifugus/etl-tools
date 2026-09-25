# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""The runtime: page furniture, locators, and the section walker."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._pattern import find_token, is_blank, line_matches
from ._recognize import convert
from ._unknown import UNKNOWN

__all__ = ["Ctx", "GridLine", "build_grid", "build_record", "find_instances",
           "locate_in_line", "resolve_field"]

# Inside the recognizers a `val` of None means "this did not read"; UNKNOWN is
# the value that reaches a caller. Keeping them distinct is what lets a
# recognizer fail over to the next rule without that failure being mistaken
# for an answer.


@dataclass(frozen=True, slots=True)
class GridLine:
    text: str
    line: int           # the PHYSICAL source line, for diagnostics


@dataclass(frozen=True, slots=True)
class Ctx:
    types: dict
    usings: dict
    trace: bool = False

    def extend(self, own: dict) -> "Ctx":
        """A binding applies to the declaring section and everything nested
        inside it, and an inner one overrides an outer."""
        return Ctx(self.types, {**self.usings, **own}, self.trace)


# ------------------------------------------------------- page furniture

def build_grid(text: str, page) -> list:
    """Strip page furniture, keeping each line's physical number.

    Runs BEFORE anything else. Everything downstream sees the clean grid, so
    ``up``/``down`` count over it and never over the physical file -- an
    offset means the same thing regardless of where a page happened to break.
    """
    grid, drop_left = [], 0
    for i, line in enumerate(text.split("\n")):
        if drop_left > 0:
            drop_left -= 1
            continue
        is_break = False
        if page.kind == "formfeed":
            is_break = "\f" in line
        elif page.kind == "regex":
            is_break = re.search(page.pattern, line) is not None
        if is_break:
            drop_left = page.drop - 1       # drop counts from and including it
            continue
        grid.append(GridLine(line, i + 1))
    return grid


# ------------------------------------------------------------- locators

def apply_columns(line: str, a: int, b: int) -> str:
    return line[a:b + 1] if a < len(line) else ""


def locate_in_line(line: str, loc: str):
    """One locator against one line.

    Returns ``{ok, span, at, anchors}`` where ``at`` is the offset of *span*
    within *line*. Every branch already knew where it cut; reporting it is
    what lets a trace point back at the source.
    """
    work, lo = line, 0

    # `<locator> within columns a-b` narrows the search window first.
    wm = re.search(r"\s+within\s+columns\s+([0-9]+)-([0-9]+)\s*$", loc)
    if wm:
        lo, hi = int(wm.group(1)), int(wm.group(2))
        work = apply_columns(line, lo, hi)
        loc = loc[:wm.start()].strip()

    cm = re.match(r"^columns\s+([0-9]+)-([0-9]+)\s*$", loc)
    if cm:
        a, b = int(cm.group(1)), int(cm.group(2))
        return {"ok": True, "span": apply_columns(work, a, b), "at": lo + a,
                "anchors": []}

    rm = re.match(r"^right\s+of\s+(.*)$", loc)
    if rm:
        m = find_token(work, rm.group(1).strip())
        if m is None:
            return {"ok": False, "span": "", "at": 0, "anchors": []}
        return {"ok": True, "span": work[m.end:], "at": lo + m.end,
                "anchors": [(lo + m.start, m.length)]}

    lm = re.match(r"^left\s+of\s+(.*)$", loc)
    if lm:
        m = find_token(work, lm.group(1).strip())
        if m is None:
            return {"ok": False, "span": "", "at": 0, "anchors": []}
        return {"ok": True, "span": work[:m.start], "at": lo,
                "anchors": [(lo + m.start, m.length)]}

    bm = re.match(r"^between\s+(.*)\s+and\s+(.*)$", loc)
    if bm:
        m1 = find_token(work, bm.group(1).strip())
        if m1 is None:
            return {"ok": False, "span": "", "at": 0, "anchors": []}
        tail = work[m1.end:]
        m2 = find_token(tail, bm.group(2).strip())
        if m2 is None:
            return {"ok": False, "span": "", "at": 0, "anchors": []}
        return {"ok": True, "span": tail[:m2.start], "at": lo + m1.end,
                "anchors": [(lo + m1.start, m1.length),
                            (lo + m1.end + m2.start, m2.length)]}

    # `first <type>` / `last <type>` -- the whole line is the span and the
    # type recognizer does the delimiting. This is the locator that survives
    # a heading adrift of its own data and a sign-widened column.
    fm = re.match(r"^(first|last)\s+([A-Za-z_]+)\s*$", loc)
    if fm:
        return {"ok": True, "span": work, "at": lo, "anchors": []}

    return {"ok": False, "span": "", "at": 0, "anchors": []}


def parse_vertical(loc: str):
    """``down <dist> of <pat> [<inner locator>]``.

    *dist* is exact (``1``), a range (``1-3``), open (``3-``, ``-8``) or
    ``flush``. A RANGE is not a convenience: in the delinquency fixture the
    gap between ``REMARKS:`` and its note is 1, 2, 2 and 3 lines across four
    branches, because the generator emits a varying number of blank lines --
    which is what real reports do. An exact distance matches one branch and
    misses the rest, silently.
    """
    vm = re.match(r"^(down|up)\s+([0-9]+-[0-9]+|[0-9]+-|-[0-9]+|[0-9]+|flush)"
                  r"\s+of\s+(.*)$", loc)
    if not vm:
        return None
    dist, rest = vm.group(2), vm.group(3).strip()

    if dist == "flush":
        lo, hi = 1, -1                                  # to the block edge
    elif re.match(r"^[0-9]+-[0-9]+$", dist):
        a, b = dist.split("-")
        lo, hi = int(a), int(b)
    elif re.match(r"^[0-9]+-$", dist):
        lo, hi = int(dist[:-1]), -1
    elif re.match(r"^-[0-9]+$", dist):
        lo, hi = 1, int(dist[1:])
    else:
        lo = hi = int(dist)

    # The anchor token is the leading "literal" or /regex/; anything after it
    # is an inner locator applied to the target line.
    inner, tok = "", rest
    tm = re.match(r'^("[^"]*"|/[^/]*/)\s*(.*)$', rest)
    if tm:
        tok, inner = tm.group(1), tm.group(2).strip()
    return {"dir": vm.group(1), "lo": lo, "hi": hi, "token": tok, "inner": inner}


# --------------------------------------------------------------- fields

_MISS = {"why": "not-found", "line": 0, "src": "", "at": 0, "length": 0}


def _miss(why, ty):
    return {"val": UNKNOWN, "why": why, "line": 0, "src": "", "at": 0,
            "length": 0, "type": ty, "anchors": []}


def resolve_field(block, f, ctx):
    """Resolve one field against a block of grid lines.

    Composing the two halves is the whole of it: the locator says where in the
    line it cut, and the converter says where in that cut the token was.
    """
    want_last, ty, loc = False, f.type, f.locator

    # `flush` reads naturally in a horizontal locator and means exactly what
    # `right of` already does. Accepted so specs can say it, then dropped.
    loc = loc.replace("right flush of ", "right of ")

    sm = re.match(r"^(first|last)\s+([A-Za-z_]+)\s*$", loc)
    if sm:
        want_last = sm.group(1) == "last"
        ty = ty or sm.group(2)

    v = parse_vertical(loc)
    if v is not None:
        return _resolve_vertical(block, v, ty, want_last, ctx)

    why = "not-found"
    for row in block:
        r = locate_in_line(row.text, loc)
        if not r["ok"]:
            continue
        got = convert(r["span"], ty, want_last, ctx)
        if got["val"] is not None:
            anchors = [(row.line, row.text, at, ln) for at, ln in r["anchors"]]
            return {"val": got["val"], "why": got["why"], "line": row.line,
                    "src": row.text, "at": r["at"] + got["at"],
                    "length": got["length"], "type": ty, "anchors": anchors}
        if got["why"]:
            why = got["why"]
    # Not found anywhere in the block: unknown, never a guess.
    return _miss(why, ty)


def _resolve_vertical(block, v, ty, want_last, ctx):
    for i, anchor_row in enumerate(block):
        hit = find_token(anchor_row.text, v["token"])
        if hit is None:
            continue
        last_off = len(block) if v["hi"] < 0 else v["hi"]
        for d in range(v["lo"], last_off + 1):
            j = i - d if v["dir"] == "up" else i + d
            if not (0 <= j < len(block)):
                continue
            span, base, r2 = block[j].text, 0, None
            if v["inner"]:
                r2 = locate_in_line(span, v["inner"])
                if r2["ok"]:
                    span, base = r2["span"], r2["at"]
            if is_blank(span):
                continue
            got = convert(span, ty, want_last, ctx)
            if got["val"] is None:
                continue
            anchors = [(anchor_row.line, anchor_row.text, hit.start, hit.length)]
            if r2 is not None and r2["ok"]:
                anchors += [(block[j].line, block[j].text, at, ln)
                            for at, ln in r2["anchors"]]
            return {"val": got["val"], "why": got["why"], "line": block[j].line,
                    "src": block[j].text, "at": base + got["at"],
                    "length": got["length"], "type": ty, "anchors": anchors}
    return _miss("anchor-not-found", ty)


# --------------------------------------------------------------- walker

def find_instances(grid, lo, hi, sec):
    """Every instance of *sec* inside [lo, hi) of the grid.

    A ``repeats`` section with no ``ends`` runs to the next occurrence of its
    OWN ``starts`` pattern, or the end of the parent -- which is what makes
    ``Branch:`` and ``Teller:`` work, since neither carries a terminator.
    """
    if not sec.starts:
        return [(lo, hi)]
    spans, i = [], lo
    while i < hi:
        if not line_matches(grid[i].text, sec.starts):
            i += 1
            continue
        j = i + 1
        while j < hi:
            halt = (line_matches(grid[j].text, sec.ends) if sec.ends
                    else line_matches(grid[j].text, sec.starts))
            if halt:
                break
            j += 1
        spans.append((i, j))
        if not sec.repeats:
            return spans
        i = j
    return spans


def _claims_for(path, f, got):
    claims = [{"path": path, "field": f.name, "kind": "field",
               "type": got["type"], "rule": f.locator, "line": got["line"],
               "start": got["at"], "length": got["length"],
               "text": got["src"][got["at"]:got["at"] + got["length"]]}]
    # An ANCHOR IS A CLAIM. A literal the spec names is the most spec-relevant
    # text on the page; left out it would sit in the unclaimed list and
    # depress coverage by exactly the literals the author wrote.
    for line, src, at, ln in got["anchors"]:
        claims.append({"path": path, "field": f.name, "kind": "anchor",
                       "type": "", "rule": f.locator, "line": line,
                       "start": at, "length": ln, "text": src[at:at + ln]})
    return claims


def build_record(grid, lo, hi, sec, ctx, path):
    """Walk one section instance into a record. Returns (rec, diags, claims)."""
    rec, diags, claims = {}, [], []
    block = grid[lo:hi]
    local = ctx.extend(sec.usings)

    # A section's own `starts` line is EXPLAINED by the spec even though no
    # field read it -- it is what located the section. Recording it as a claim
    # keeps a heading out of the unclaimed list, where it would read as text
    # the spec had missed.
    if ctx.trace and sec.starts:
        hm = find_token(grid[lo].text, sec.starts)
        if hm is not None:
            claims.append({"path": path, "field": "", "kind": "section",
                           "type": "", "rule": sec.starts, "line": grid[lo].line,
                           "start": hm.start, "length": hm.length,
                           "text": grid[lo].text[hm.start:hm.end]})

    for f in sec.fields:
        got = resolve_field(block, f, local)
        rec[f.name] = got["val"]
        if got["val"] is UNKNOWN:
            diags.append({"path": f"{path}.{f.name}", "reason": got["why"],
                          "line": grid[lo].line})
        elif ctx.trace:
            claims += _claims_for(f"{path}.{f.name}", f, got)

    if sec.has_rows:
        rec["rows"], row_diags, row_claims = _build_rows(grid, lo, hi, sec, local, path, ctx)
        diags += row_diags
        claims += row_claims

    for child in sec.sections:
        spans = find_instances(grid, lo, hi, child)
        if child.repeats:
            items = []
            for idx, (a, b) in enumerate(spans):
                sub = build_record(grid, a, b, child, local, f"{path}.{child.name}[{idx}]")
                items.append(sub[0])
                diags += sub[1]
                claims += sub[2]
            rec[child.name] = items
        elif not spans:
            rec[child.name] = UNKNOWN
            diags.append({"path": f"{path}.{child.name}",
                          "reason": "section-not-found", "line": grid[lo].line})
        else:
            sub = build_record(grid, spans[0][0], spans[0][1], child, local,
                               f"{path}.{child.name}")
            rec[child.name] = sub[0]
            diags += sub[1]
            claims += sub[2]

    return rec, diags, claims


def _build_rows(grid, lo, hi, sec, local, path, ctx):
    """``rows:`` -- one record per remaining line, emitted as a FRAME.

    Columns of equal length rather than a list of records, because that is
    what a dataframe consumes: ``polars.DataFrame(rec["rows"])`` and
    ``pandas.DataFrame(rec["rows"])`` both take it directly, with no
    dependency on either from here.
    """
    cols = {rf.name: [] for rf in sec.rows}
    diags, claims = [], []
    # The section's own `starts` line belongs to the section and is NOT
    # offered to its rows, or the column heading becomes a data row.
    k = lo + 1 if sec.starts else lo
    ridx = 0
    while k < hi:
        if is_blank(grid[k].text):
            k += 1
            continue
        # A logical row is a BLOCK of lines, not necessarily one. With no
        # `continue` pattern that block is always a single line; with one,
        # wrapped lines are absorbed into the record above, and every locator
        # -- including the vertical ones -- works inside it unchanged.
        first_line = grid[k].line
        one = [grid[k]]
        k += 1
        if sec.row_continue:
            while k < hi and not is_blank(grid[k].text) \
                    and line_matches(grid[k].text, sec.row_continue):
                one.append(grid[k])
                k += 1
        for rf in sec.rows:
            got = resolve_field(one, rf, local)
            cols[rf.name].append(got["val"])
            rp = f"{path}.rows[{ridx}].{rf.name}"
            if got["val"] is UNKNOWN:
                diags.append({"path": rp, "reason": got["why"], "line": first_line})
            elif ctx.trace:
                claims += _claims_for(rp, rf, got)
        ridx += 1
    return cols, diags, claims
