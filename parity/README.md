# The parity harness

One case file, two runners. A promise that two libraries behave alike decays;
a test of it does not.

```bash
python parity/run_parity.py                                   # this tree
gbasic parity/run_parity.bas parity/cases/money.tsv           # the gBASIC tree
```

Both read the *same* files from `cases/`. A case that disagrees fails in
whichever tree is wrong, and the case file arbitrates — neither implementation
is right merely by being the one that was asked.

## The format is tab-separated, on purpose

JSON was the first instinct and was wrong. gBASIC's `crypto.json_decode` is
documented as *flat*, so a nested case file would have been readable by one
side only — and a harness whose two halves disagree about how to read the
questions cannot arbitrate the answers.

```
expr <TAB> ccy <TAB> amount <TAB> operand <TAB> expect <TAB> name
```

`operand` is `-` when unused. An `expect` beginning with `!` is an error, and
the rest is its message **verbatim** — error text is part of the public surface
(`porting-plan.md` §1.1).

## Known upstream defects

A `name` beginning with `gbasic-defect:` marks a case this tree passes and
gBASIC is known to fail. It is a hard failure on the Python side and a
reported-but-tolerated divergence on the gBASIC side, which is the right
asymmetry when the defect is upstream. It cannot be forgotten, because every
run prints it.

There is one, found by this harness on its first run: gBASIC's two money
constructors give different messages for the same refusal.

```
{USD}= "1.23456789"              -> USD: money text has more decimal places
                                    than the currency can store (USD stores 6)
money.of("USD", "1.23456789")    -> money text has more decimal places than
                                    the currency can store
```

`reference.md` says `money.of` has "the same parse path and same refusals as
the modifier". The refusal is the same; the message is not. The expectation in
`cases/money.tsv` is the modifier's, because it names the currency and the
limit, and the fix belongs in gBASIC.
