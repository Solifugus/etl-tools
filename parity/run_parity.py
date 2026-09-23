#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Run the shared parity cases against the Python tree.

Its twin, ``run_parity.bas``, runs the *same files* against gBASIC. A case that
disagrees fails in whichever tree is wrong, and the case file is the arbiter --
neither implementation gets to be right merely by being the one that was asked.

**The format is tab-separated, deliberately.** JSON was the first instinct and
was wrong: gBASIC's ``crypto.json_decode`` is documented as flat, so a nested
case file would have been readable by one side only, and a harness whose two
halves disagree about how to *read* the questions cannot arbitrate the answers.
Six tab-separated columns are unambiguous in both.

    expr <TAB> ccy <TAB> amount <TAB> operand <TAB> expect <TAB> name

``operand`` is ``-`` when unused. An ``expect`` starting with ``!`` is an
error and the rest is its message, verbatim -- error text is part of the public
surface (``porting-plan.md`` §1.1).

A ``name`` starting with ``gbasic-defect:`` marks a case this tree passes and
gBASIC is known to fail. It is a full failure here and a reported-but-tolerated
divergence there, which is the right asymmetry when the defect is upstream.

Usage:  python parity/run_parity.py [cases/money.tsv ...]
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "packages" / "tervalue"))

from tervalue import Money  # noqa: E402


def _num(text: str):
    """An operand is an int when it looks like one, else a Decimal."""
    return int(text) if text.lstrip("-").isdigit() else Decimal(text)


MONEY = {
    "show":   lambda c, a, _: str(Money.of(c, a).posted),
    "text":   lambda c, a, _: Money.of(c, a).text(),
    "text2":  lambda c, a, _: Money.of(c, a).text(2),
    "mul":    lambda c, a, n: str((Money.of(c, a) * _num(n)).posted),
    "div":    lambda c, a, n: str((Money.of(c, a) / _num(n)).posted),
    "divmul": lambda c, a, n: str((Money.of(c, a) / _num(n) * _num(n)).posted),
    "accum":  lambda c, a, n: str(sum((Money.of(c, a) for _ in range(int(n))),
                                      Money.zero(c)).posted),
}

EVALUATORS = {"money": MONEY}


def run_file(path: Path) -> tuple[int, int, int]:
    table = EVALUATORS.get(path.stem)
    passed = failed = skipped = 0
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.startswith("#") or raw.startswith("expr\t"):
            continue
        expr, ccy, amount, operand, expect, name = raw.split("\t")
        fn = (table or {}).get(expr)
        if fn is None:
            skipped += 1
            continue
        try:
            got = fn(ccy, amount, operand)
        except Exception as e:                  # noqa: BLE001 - reported, not swallowed
            got = "!" + str(e)
        if got == expect:
            passed += 1
            # A gbasic-defect case is one Python gets right and gBASIC does
            # not. It must pass *here*; the gBASIC runner reports it as known.
        else:
            failed += 1
            print(f"  FAIL {name}\n       want {expect}\n       got  {got}")
    return passed, failed, skipped


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    files = [Path(a) for a in argv] or sorted((ROOT / "cases").glob("*.tsv"))
    tp = tf = ts = 0
    for f in files:
        p, q, s = run_file(f)
        print(f"{f.name}: {p} passed, {q} failed" + (f", {s} skipped" if s else ""))
        tp, tf, ts = tp + p, tf + q, ts + s
    print(f"\npython: {tp} passed, {tf} failed, {ts} skipped")
    return 1 if tf else 0


if __name__ == "__main__":
    sys.exit(main())
