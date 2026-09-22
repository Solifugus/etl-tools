# Porting gBASIC's libraries to Python — development plan

**Status:** Proposal (2026-09-22). Nothing below is committed scope.\
**Path:** `docs/porting-plan.md`\
**Companion:** `docs/etools-design.md` (the architecture this fills in)\
**Source tree surveyed:** `~/development/gbasic` @ `4e8cce8`, 64 stdlib
libraries, 51,219 lines of `.bas`.

---

## 1. The governing constraint

> "similarly so learning one makes it similar to learning the other"

That is not a nice-to-have, it is the **hardest** constraint in this document,
and it is the one that will be under pressure in every phase. Every time a
Python idiom is more comfortable than the gBASIC shape, parity is what pays
for the comfort. So the rule is stated once, here, and appealed to by name:

**Same library name. Same function name. Same argument order. Same return
field names. Same error text.** What changes is only the *spelling of the
mechanism*, and only where Python gives the identical guarantee for free.

### 1.1 The translation law

| gBASIC | Python | Why this is still parity |
|---|---|---|
| `library dates` | module `etools.dates` | Library ≙ module, name unchanged. |
| `dates.add_business_days(d, n, cal)` | `dates.add_business_days(d, n, cal)` | Identical call, read aloud identically. |
| `options` record + `_options(rec, known, label)` | keyword-only arguments | gBASIC raises on an unknown field; Python raises `TypeError` on an unexpected keyword. **Same guarantee, enforced by the language instead of by hand.** |
| `unknown` (native NA) | `etools.core.UNKNOWN` singleton | `None` already means "nothing was supplied". Axiom 7 needs "a value exists and is not known" to be a *different* thing. Conflating them would break the axiom in the first module. |
| `{ status:, value:, raw:, source: }` | frozen dataclass `Outcome` with those four field names | Three-valued results survive as data, not as exceptions. |
| record `{}` | `dict` | A frame stays a dict of columns. **No new value kind** — `frame.bas`'s own rule, and the reason `mean(df.age)` just works there and `mean(df["age"])` just works here. |
| `error "finio.open_text: unknown field 'x'"` | `raise ValueError` with the *same string* | Error text is part of the public surface. A user who has read one project's message has read the other's. |
| money `{USD}` (int64 minor units) | `Money(Decimal, currency)` | Exact integer minor units; construction from `float` refused, as `money_design.md` §2 requires. |

### 1.2 The three sanctioned deviations

Everything else is parity. These three are allowed, and each must be recorded
in the module's docstring where it occurs:

1. **Python keywords.** A gBASIC identifier that is a Python keyword takes a
   trailing underscore: `pois_pmf(k, lambda)` → `pois_pmf(k, lambda_)`. There
   are fewer than a dozen of these across the whole surface.
2. **Iterators where gBASIC materialises.** `finio` must stream a 9.5 MB file;
   returning a generator where gBASIC returns a list is permitted **only** when
   the function is documented as streaming in both trees.
3. **`Decimal` where gBASIC has a native numeric.** gBASIC's interpreter gives
   exactness in the language; Python has to ask for it.

A fourth deviation is *not* sanctioned and is called out because it is the
tempting one: **do not "improve" an API during the port.** If a signature is
wrong, fix it in gBASIC first, then port the fixed one. Two libraries that
drift are worse than one library.

---

## 2. Triage — what happens to each of the 64

Three treatments, plus what is already built. The distinction matters more
than the phasing does: **most of this tree should not be re-implemented.**

### 2.1 PORT — Python has no good equivalent (≈19,700 lines)

The real work. These are ported line-for-line in behaviour, with the gBASIC
fixtures as the test corpus.

| Group | Modules | Lines | Becomes |
|---|---|---|---|
| finio framework | `finio` `finio_registry` `finio_watch` `finio_all` | 1,954 | `etools.formats`, `etools.registry` |
| finio adapters | `finio_nacha` `finio_bai2` `finio_camt` `finio_ofx` `finio_pain001` `finio_iso20022` | 4,205 | `etools.adapters.*` |
| value layer | `notation` `dates` `persist` | 2,028 | `etools.notation`, `etools.dates`, `etools.persist` |
| structural | `frame` `fake` | 1,561 | `etools.frame`, `etools.fake` |
| finance math | `finance` `accounting` | 1,084 | `etools.finance`, `etools.accounting` |
| domain | `credit` `scoring` `lending` `estate` `deposits` | 2,157 | `etools.domain.*` |
| lineage | `discovery` | 2,342 | folds into the existing `etools.lineage` |
| spreadsheet→DB | `consolidate` `dbframe` | 626 | `etools.transform`, `etools.db.frame` — **AGPL, see §4** |
| EDGAR suite | `edgar` `fundamentals` `screener` `forensics` `insiders` `ownership` `mdna` | 3,251 | `etools.sources.edgar`, `etools.analysis.*` — **AGPL, see §4** |
| retrieval | `market` | 471 | `etools.sources.market` |

Plus the **`money` language type**, which has no `.bas` file — it lives in
`src/eval.c` and `docs/money_design.md`. It ports as `etools.core.money`, and
it ports **first**, because six of the groups above return one.

### 2.2 SHIM — same names over an existing Python library

Parity of *vocabulary* without re-implementing solved problems. A shim module
exports the gBASIC function names and delegates. Each is an optional extra, so
the stdlib-core rule holds.

| Module | Lines | Delegates to | Why not port |
|---|---|---|---|
| `stats` | 9,363 | `scipy` + `statsmodels` | 225 functions of distributions, GLMs, PCA, k-means. Re-deriving `t_cdf` against scipy is work with a known answer and a worse error bar. |
| `matrix` | 232 | `numpy` | Same. |
| `chart` | 1,612 | emit Vega-Lite specs | gBASIC renders because it must; Python should hand a spec to something that renders. |
| `gpdf` `gpdf_metrics` | 1,612 | `reportlab` | |
| `ocr` | 531 | `pytesseract` | |
| `crypto` `otp` | 772 | `hashlib`, `cryptography`, `pyotp` | Port **only** `sign_cookie`/`csrf_*`/`jwt_*` conveniences if a consumer appears. Never hand-roll the primitives. |
| `web` `mail` | 1,761 | `httpx`/`smtplib` | `etools.core.http` already covers the ETL need. |

**`stats` is the single biggest decision in this section.** Shimming it means
`etools.stats.t_test_welch(xs, ys)` reads the same in both trees and returns the
same field names, while scipy does the arithmetic. That is the parity the
constraint actually asks for, at about 3% of the cost of porting.

### 2.3 SKIP — bound to the language or to a GUI

`gui` `gtk` `gtkui` `gtksourceview` `sourceeditor` `datagrid` `grid`
`filetree` `tools` `schedule`, and the entire AI layer: `llm` `mcp` `agent`
`ari` `ari_advisor` `ari_discover` `reasoning` `decision` `insight`
`automation` `nlq` `retrieval`.

The AI layer is skipped **as a scope decision, not a value judgement** — it is
a coherent project of its own, and folding it into an ETL library would make
the ETL library something else. Revisit it as a separate distribution.

### 2.4 ALREADY BUILT

`etools.sources.treasury`, `etools.sources.fred`, `etools.db.rates`,
`etools.lineage`, `etools.core.http`, `etools.core.run`. These have no gBASIC
counterpart and set the house style the ports should match.

---

## 3. The parity harness — how the constraint stays true

A promise of parity decays. A **test** of parity does not.

`tests/parity/cases/*.json` holds cases that are executable by *both* trees:

```json
{ "module": "dates", "function": "add_business_days",
  "args": ["2026-09-18", 3, {"weekend": ["Sat", "Sun"], "holidays": []}],
  "expect": "2026-09-23" }
```

Two runners consume the same file:

- `tests/parity/run_parity.py` — calls `etools.<module>.<function>(*args)`
- `tests/parity/run_parity.bas` — calls the gBASIC library, lives in the
  gBASIC tree and is run from there

A divergence fails the suite in whichever tree is wrong, and the case file is
the arbiter. This is `odbc_cookbook.md`'s **"this page cannot lie"** applied
across two implementations instead of across one document.

It also solves the fixture problem for free: `~/development/gbasic/examples/fixtures/`
already holds NACHA, EDGAR, xlsx and XML corpora that the gBASIC suite trusts.
The port reuses them rather than inventing new ones, so "the Python NACHA reader
agrees with the gBASIC one" is checked against bytes both trees have already
read.

**Phase 0 builds this before anything is ported.** A harness added after the
fact only ever tests what already passes.

---

## 4. The licensing gate — decide before Phase 6

Ten gBASIC libraries are **AGPL-3.0-or-later**, not Apache-2.0:
`consolidate` `dbframe` `edgar` `forensics` `fundamentals` `grid` `insiders`
`mdna` `ownership` `screener`. That is the spreadsheet→database pipeline and
the whole EDGAR securities-analysis suite — about 3,880 portable lines, and
some of the most distinctive work in the tree.

`etools` is Apache-2.0. **These cannot simply be copied across.** The copyright
holder is the same person, so this is a decision, not an obstacle — but it has
to be a deliberate one:

| Option | Effect | Cost |
|---|---|---|
| **A. Relicense the ports to Apache-2.0** | They ship in `etools` like everything else. | Gives up the AGPL's reciprocity on exactly the code that was singled out for it. |
| **B. Second distribution, `etools-edgar`, AGPL** | Keeps the original bargain; `etools` core stays Apache. | Two distributions, two licenses, and the banks `etools` targets cannot use it. |
| **C. Defer** | Phases 0–7 are entirely Apache-2.0 and unblocked. | The EDGAR work waits. |

**Recommended: C now, A later.** Nothing before Phase 8 touches an AGPL module,
so the decision does not need making today — and it is a better decision after
the framework exists than before. When it comes: the AGPL was chosen to protect
a *product*; `etools` is a *component*, and a component nobody may import is not
protected, it is unused.

---

## 5. Phases

Following gBASIC's own `PLAN.md` conventions: **one phase per session**, full
suite green at every boundary, **✋ STOP** for review at each.

### Phase 0 — The contract

No ported logic. Build the things every later phase depends on.

- [ ] `docs/porting-plan.md` reviewed and the translation law (§1.1) ruled on.
- [ ] `etools/core/values.py`: `UNKNOWN`, `Outcome`, `LossReport`.
- [ ] `etools/core/money.py`: exact minor units, `float` construction refused,
      per-currency scale, rounding rule stated and tested at `.5`.
- [ ] `tests/parity/` with both runners and **one** real case end to end.
- [ ] Parity case format frozen and documented.

**Exit:** a case file fails in both trees when the expectation is wrong, and
passes in both when it is right. ✋ STOP.

### Phase 1 — The value layer

- [ ] `notation` (`to_text`/`from_text`/`try_from_text`) — needed first because
      the parity harness serialises through it.
- [ ] `dates` — business calendars, `series`, `matches`, business *hours*.
      The highest-value single port: Python has nothing this good without
      pulling in a heavyweight dependency.
- [ ] `persist` — atomic writes.

**Exit:** ≥60 parity cases across the three. ✋ STOP.

### Phase 2 — finio, the framework

The port that everything financial rests on. Port the *decisions*, not just the
code — §4 source retention, byte offsets (never codepoints), framing as
recognition rather than assumption, the read/validate split, loss primitives.

- [ ] `finio` core: `open_text`, source retention, byte-offset slicing.
- [ ] Recognition: candidates + evidence, classification
      `exact`/`strong`/`possible`/`ambiguous`/`unknown`.
- [ ] `finio_registry`: formats as rows, not functions (axiom 5).
- [ ] Per-cell provenance opt-in, reconstructed on demand — the measured design
      (`examples/finio_lab/provenance_cost.bas`), not the stored one.

**Exit:** the provenance cost measurement re-run in Python, with the result
recorded in the design doc whether or not it agrees. Multi-session. ✋ STOP.

### Phase 3 — The adapters

In gBASIC the framework and its first adapter shipped **together**, because a
framework with an imaginary consumer cannot be tested. Same rule here.

- [ ] `finio_nacha` (1,113 lines — the reference adapter, ships with Phase 2).
- [ ] `finio_bai2`, then `finio_ofx`, `finio_camt`, `finio_pain001`.
- [ ] Byte-fidelity round-trip on the shared fixtures: read then write must
      reproduce the input file, terminators included.

**Exit:** round-trip byte-identical on every fixture. Multi-session. ✋ STOP.

### Phase 4 — Structure and test data

- [ ] `frame` — dict of columns, `unknown` for missing, every transform
      returning a new frame.
- [ ] `fake` — deterministic generators keyed by `(base, i)`. Unlocks realistic
      test corpora for every later phase, which is why it comes before them.

**Exit:** `frame.read_csv` → `summarize` → `join` → `write_csv` parity. ✋ STOP.

### Phase 5 — Finance mathematics

- [ ] `finance` — TVM, `npv`/`irr`/`xnpv`/`xirr`, day-count conventions,
      depreciation.
- [ ] `accounting` — chart, entries, ledger, trial balance, statements, close.

The easiest phase to verify and the best parity demonstration in the plan:
every function has a closed-form answer and no I/O. ✋ STOP.

### Phase 6 — The domain layer

- [ ] `lending`, `deposits` — amortisation, events, payoff, tiered interest.
- [ ] `credit` — delinquency buckets, migration, roll rates, vintage.
- [ ] `scoring` — WOE/IV, KS, AUC, scorecard scaling, PSI.
- [ ] `estate`.

**Exit:** a worked scorecard reproduced from gBASIC's cookbook. ✋ STOP.

### Phase 7 — Lineage, properly

`discovery` (2,342 lines) is SQL-level lineage: parse, reference extraction,
projection, predicates, derivations, `trace`, `impact`, column-level `lineage`.
This is **the** differentiator, and it merges with the OpenLineage-shaped graph
`etools.lineage` already has: `discovery` finds edges statically from SQL,
`run.py` records them dynamically at execution. Neither alone is lineage.

- [ ] Port `discovery`'s extraction over the existing `LineageStore`.
- [ ] Reconcile static and observed edges; disagreement is a **finding**, not
      an error to be smoothed over.

**Exit:** a column traced from source file to database column across both
mechanisms. Multi-session. ✋ STOP.

### Phase 8 — Sources, and the licensing gate

- [ ] `market` (stooq/tiingo, with the offline transport — Apache-2.0, clear).
- [ ] **Gate:** §4 decided before any EDGAR line is written.
- [ ] `edgar`, `fundamentals`, `screener`, `forensics`, `insiders`,
      `ownership`, `mdna`.

### Rolling — the shims

Not a phase; done whenever a consumer needs one. `stats` first, because it is
the one most likely to be reached for.

---

## 6. Honest sizing

≈19,700 lines of `.bas` in the PORT column, plus tests and parity cases.
Phases 2, 3 and 7 are each multi-session on their own. Realistically **15–20
focused sessions**, not nine.

The shim column removes about 15,900 lines from that estimate. It is where the
plan's leverage is, and it deserves more scepticism than the porting does:
if the shims feel wrong in use, the sizing changes materially.

---

## 7. Open decisions

Carried from `docs/etools-design.md` §11, answered where the last month of
building has settled them:

1. **One distribution or several?** → **One**, `etools-etl`, with extras
   (`[postgres]`, `[stats]`, `[charts]`). Revisit only if §4 lands on option B.
2. **`db/` targets T-SQL or Postgres first?** → **Postgres**, de facto: it is
   what slice 1 loads into and what has been verified end to end.
3. **Python floor?** → **3.11** (`tomllib`, `Self`, exception groups).

New, and genuinely open:

4. **Does `stats` shim or port?** §2.2 recommends shim. This is the decision
   most likely to be wrong, and the cheapest to reverse early.
5. **Where do the parity cases live** — this repo, the gBASIC repo, or a third
   one both consume? A third is cleanest and is one more thing to maintain.
6. **Does a gBASIC API fix block its Python port?** §1.2 says yes — fix
   upstream, then port. That will be annoying at least once. Confirm now,
   while it is hypothetical.
