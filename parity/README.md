# The parity harness

One case file, two runners. A promise that two libraries behave alike decays;
a test of it does not.

```bash
python parity/run_parity.py                                   # this tree
gbasic parity/run_parity.bas parity/cases/*.tsv               # the gBASIC tree
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
expr <TAB> a <TAB> b <TAB> c <TAB> expect <TAB> name
```

What the middle three columns mean depends on `expr`; an unused one is `-`.
An `expect` beginning with `!` is an error, and the rest is its message
**verbatim** — error text is part of the public surface
(`porting-plan.md` §1.1).

## Named calendars and specs

Six flat columns cannot carry "the third Thursday of every month at 14:00,
rolled off this calendar's holidays". So `cases/dates.tsv` names its
calendars, specs and bounds, and **both runners build the named thing
identically** — `run_parity.py`'s `CALENDARS`/`SPECS`/`BOUNDS` tables and
`run_parity.bas`'s `_dcal`/`_dspec`/`_dbounds` functions.

That is not only a workaround for the format. It means a case that disagrees
is a disagreement about *behaviour*, never about which calendar was meant —
the failure mode where both sides are right about different questions is
designed out.

`cases/dates.tsv` needs `stdlib/dates.bas`, loaded relative to the runner as
`../../gbasic/stdlib/dates.bas`. Sibling checkouts, which is what running the
harness in both trees already assumes.

## Known upstream defects

A `name` beginning with `gbasic-defect:` marks a case this tree passes and
gBASIC is known to fail. It is a hard failure on the Python side and a
reported-but-tolerated divergence on the gBASIC side, which is the right
asymmetry when the defect is upstream. It cannot be forgotten, because every
run prints it.

### money — two constructors, two messages

Found by the harness on its first run: gBASIC's two money constructors give
different messages for the same refusal.

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

### dates — silent guesses where the house pattern refuses

Two more, found porting `stdlib/dates.bas`. Both are the same shape, and it is
a shape worth naming: `dates.bas` reads its records with `has(spec, "...")`,
so a key it does not recognise is **silently ignored**. Eleven other gBASIC
stdlib libraries refuse unknown options through `_options()`, naming the known
set — so this is an inconsistency rather than an intent.

| spec | gBASIC answers | should be |
|---|---|---|
| `{ nth: 3, weekdy: "thursday", within: "month" }` | `2026-08-03` | a refusal |
| `{ nth: "first", weekday: "thursday", within: "month" }` | `2026-08-27` | a refusal |

The first is the dangerous one. A misspelled `weekday` does not fail — it
quietly turns "the third Thursday of the month" into "the third *day* of the
month", and a payment schedule built on it looks entirely plausible until
somebody checks a calendar. The second returns the *last* Thursday, because
`_nth_num` maps any string at all to −1.

Axiom 6: never silently guess. Python refuses both, and there is a third that
does not appear in the table because Python's own `TypeError` text is not
stable enough to pin in a case file: `dates.calendar({ holidayz: [...] })`
silently yields a calendar with no holidays, where keyword-only arguments
refuse it by construction.

All three fixes belong in `dates.bas`, upstream.

### persist — one temp filename for every writer

`write_atomic` and `write_text_atomic` write to a **fixed** `path + ".tmp"`
and rename it into place. The rename is genuinely atomic; the temp name is
the problem. Two processes writing one store open the same temp file, so the
loser's rename publishes bytes the winner was halfway through writing — which
is the exact failure the temp-then-rename dance exists to prevent. A crashed
run also strands `settings.json.tmp` beside the store forever.

Python writes to a unique sibling (`name.<pid>.<random>.tmp`) and unlinks it
if anything fails, so each writer renames its own whole file. Not in the case
file — a temp filename is not observable in a passing case — but covered by
`test_concurrent_writers_never_interleave`, which runs two writers and a
reader against one store and asserts the reader never sees a torn file.

## Where the two trees deliberately differ

Not every divergence is a defect. `cases/persist.tsv` compares the *three-way
classification* of a store — loaded, missing, corrupt — rather than the words,
because `read_status` returns gBASIC's `{status, value, message}` record there
and a `tervalue.Outcome` here:

| gBASIC | here | why |
|---|---|---|
| `"loaded"` | `is_ok` | |
| `"missing"` | `is_unknown` | a store that is absent is not a store that is wrong — axiom 7 |
| `"corrupt"` | `is_invalid` | and `Outcome` *enforces* that an invalid carries a reason |

Both runners map into the case file's vocabulary, which is stated at the top
of that file. The naming deviation itself is covered by the unit tests and
`etools/persist.py`'s docstring — a case file is the wrong place to pin a
decision, because it would read as an accident.
