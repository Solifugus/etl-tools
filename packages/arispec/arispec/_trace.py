# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""The span report: what a specification explained, and what it missed.

Measured against the source rather than against the inference that produced
the spec -- estimating it from the model that generated the spec would be the
tool grading its own homework.

**Blanks are not content.** A print image is largely column padding, so
counting it would put every specification's coverage near 1.0, which is the
flattering-and-useless direction. And a control character is not content
either: the one that matters is the FORM FEED, which is page furniture by
definition and survives into the grid whenever a report is paginated by a
header line rather than by the feed itself. Counted as content it produces a
run whose text trims to nothing -- not a finding, just the printer.
"""

from __future__ import annotations

from collections import defaultdict

__all__ = ["collisions", "coverage"]


def _blank_char(c: str) -> bool:
    return c.isspace() or ord(c) < 32


def _nonblank_in(text: str, a: int, b: int) -> int:
    return sum(1 for c in text[a:b] if not _blank_char(c))


def _by_line(claims):
    out = defaultdict(list)
    for c in claims:
        out[c["line"]].append(c)
    return out


def _covered_at(claims, i: int) -> bool:
    return any(c["start"] <= i < c["start"] + c["length"] for c in claims)


def coverage(grid, claims) -> dict:
    """Non-blank characters the spec explained, and the runs it did not.

    Each unclaimed run carries its own size AND its line's, both counted by
    the same rule -- so a caller asking "is this the whole line?" needs no
    second notion of what a blank is, and a second notion is exactly what
    would drift.
    """
    by_line = _by_line(claims)
    total = covered = 0
    runs = []

    for g in grid:
        cs = by_line.get(g.line, ())
        line_nb = 0
        mine = []
        run_start = run_end = -1
        for i, ch in enumerate(g.text):
            if _blank_char(ch):
                continue
            total += 1
            line_nb += 1
            if _covered_at(cs, i):
                covered += 1
                if run_start >= 0:
                    mine.append(len(runs))
                    runs.append(_run(g, run_start, run_end))
                    run_start = -1
            else:
                if run_start < 0:
                    run_start = i
                run_end = i + 1
        if run_start >= 0:
            mine.append(len(runs))
            runs.append(_run(g, run_start, run_end))
        # The line's own size is only known once the line is walked.
        for ri in mine:
            runs[ri]["line_chars"] = line_nb

    return {"content_chars": total, "claimed_chars": covered,
            "fraction": (covered / total) if total else None,
            "unclaimed": runs}


def _run(g, a: int, b: int) -> dict:
    return {"line": g.line, "start": a, "length": b - a, "text": g.text[a:b],
            "chars": _nonblank_in(g.text, a, b), "line_chars": 0}


def collisions(claims) -> dict:
    """Spans two rules both explained -- so at least one must be wrong.

    THE VALUE CONDITION IS WHAT MAKES THE MEASURE MEAN ANYTHING, and it went
    in after measuring: structural markers overlapping each other is
    ORDINARY. A section declared ``starts(/^Branch: /)`` beside a field read
    ``right of "Branch:"`` names the same seven characters twice ON PURPOSE,
    and counting that made three correct headings the entire reported rate on
    a specification with nothing wrong with it. A number that fires on the
    commonest correct shape in the language is noise with a name.

    So a collision needs a value on at least one side, and the two claims must
    come from different paths.
    """
    found, involved = [], set()
    for cs in _by_line(claims).values():
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                a, b = cs[i], cs[j]
                if a["path"] == b["path"]:
                    continue
                if a["kind"] != "field" and b["kind"] != "field":
                    continue
                lo = max(a["start"], b["start"])
                hi = min(a["start"] + a["length"], b["start"] + b["length"])
                if lo >= hi:
                    continue
                found.append({"line": a["line"], "start": lo, "length": hi - lo,
                              "text": a["text"][lo - a["start"]:hi - a["start"]],
                              "paths": (a["path"], b["path"])})
                involved.update((a["path"], b["path"]))

    values = sum(1 for c in claims if c["kind"] == "field")
    n = sum(1 for c in claims if c["kind"] == "field" and c["path"] in involved)
    return {"collisions": found, "involved": n, "values": values,
            "rate": (n / values) if values else None}
