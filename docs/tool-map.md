# The tool map — everything `etools` is meant to contain

**Status:** Inventory (2026-09-23). Descriptive, not a commitment.\
**Path:** `docs/tool-map.md`\
**Sources reconciled:** `docs/etools-design.md` §4/§7/§8 and
`docs/porting-plan.md` §2, plus the code actually on disk.

> **Predates `docs/roadmap.md` (2026-09-23),** which re-verdicts several rows
> against existing Python libraries. Where they disagree, the roadmap wins:
> `ari` and the xlsx stack are builds, and `stats`/`xml`/`chart` and friends
> are adoptions rather than shims written here.

---

## Why this document exists

Before it, the answer to "what are we building?" lived in three places that
each saw a different part of it:

| Where | What it maps | What it cannot see |
|---|---|---|
| `etools-design.md` §4 | Ten subpackages, one line each | Contents — it is a shape, not a list |
| `etools-design.md` §7-8 | Four slices | Anything past a sentence fragment |
| `porting-plan.md` §2 | 64 gBASIC libraries, triaged | **Anything with no gBASIC ancestor** |

That last blind spot is the important one. The porting plan is organised by
gBASIC origin, so a tool gBASIC never had is structurally invisible in it —
and **a third of the intended surface is exactly that.** `quality/` has no
gBASIC ancestor at all. Neither do ISO 8583, SWIFT MT or X9.37, though §8
lists them in the same breath as NACHA, which `finio` does cover.

Columns below: **BUILT** (on disk now), **port:*x*** (from gBASIC `x`),
**shim:*x*** (gBASIC names over a Python library), **NEW** (no ancestor —
has to be designed, not translated).

---

## 1. `core/` — the shared machinery

| Tool | Origin | Phase |
|---|---|---|
| `http.get` — retry, backoff, on-disk cache, per-source UA policy | **BUILT** | — |
| `run` / `current` — ambient run context, ContextVar | **BUILT** | — |
| `http` rate limiting — token bucket, per host | **NEW** | 0 |
| `UNKNOWN`, `Outcome`, `LossReport` — axioms 7-8 as values | port:`finio` | 0 |
| `money` — exact minor units, float construction refused | port:*(eval.c)* | 0 |

## 2. Ported libraries — top level, named for their gBASIC original

The translation law (`porting-plan.md` §1.1) requires `library dates` to become
`etools.dates`, not `etools.core.dates`. See §8 below — this collides with the
design doc's layout and needs a ruling.

| Tool | Origin | Phase |
|---|---|---|
| `notation` — `to_text` / `from_text` / `try_from_text` | port:`notation` | 1 |
| `dates` — business calendars, `series`, `matches`, business *hours* | port:`dates` | 1 |
| `persist` — atomic writes | port:`persist` | 1 |
| `frame` — dict-of-columns, `unknown` for missing, no new value kind | port:`frame` | 4 |
| `fake` — deterministic generators keyed by `(base, i)` | port:`fake` | 4 |
| `finance` — TVM, `npv`/`irr`/`xnpv`/`xirr`, day counts, depreciation | port:`finance` | 5 |
| `accounting` — chart, entries, ledger, trial balance, statements | port:`accounting` | 5 |
| `stats` — 225 functions | shim:`scipy`+`statsmodels` | rolling |
| `matrix` | shim:`numpy` | rolling |

## 3. `formats/` — representation (bytes)

| Tool | Origin | Phase |
|---|---|---|
| `finio` core — source retention, byte offsets, framing-as-recognition | port:`finio` | 2 |
| `recognize(path)` — candidates + evidence, never a silent guess (axiom 10) | port:`finio` | 2 |
| `fixedwidth` | port:`finio` | 2 |
| `delimited` — CSV/TSV with dialect sniffing **and retained source** | **NEW** | 2 |
| `xlsx` | shim:`openpyxl` | rolling |
| `xml` / `json` | shim:*(stdlib)* | rolling |

## 4. `adapters/` — meaning

| Tool | Origin | Phase |
|---|---|---|
| `nacha` — ACH, the reference adapter | port:`finio_nacha` | 3 |
| `bai2` — bank statements | port:`finio_bai2` | 3 |
| `ofx` | port:`finio_ofx` | 3 |
| `camt` / `pain001` / `iso20022` | port:`finio_*` | 3 |
| `iso8583` — card messages | **NEW** | 3+ |
| `swift_mt` — MT103/MT940/MT942 | **NEW** | 3+ |
| `x937` — cheque images, Check 21 | **NEW** | 3+ |

**The three NEW rows are the surprise in this document.** §8 of the design doc
lists them alongside NACHA as though they were one body of work. They are not:
NACHA is a translation with a passing test suite behind it, and these three are
original implementations of specifications nobody here has written yet. They
should not share a phase with the ports, and their sizing is unknown.

## 5. `sources/` — network retrieval

| Tool | Origin | Phase |
|---|---|---|
| `treasury.yields` — the daily curve, 11 tenors | **BUILT** | — |
| `fred.series` / `latest` | **BUILT** | — |
| `market` — stooq / tiingo, with an offline transport | port:`market` | 8 |
| `edgar` — CIK, submissions, company facts, documents | port:`edgar` **AGPL** | 8 |
| `fundamentals` / `screener` / `insiders` / `ownership` / `mdna` | port:* **AGPL** | 8 |
| `fdic.call_report` | **NEW** | 8+ |
| `ffiec` | **NEW** | 8+ |

## 6. `db/` — movement and profiling

The least-mapped area relative to its stated importance. §4 gives it one line;
§8 calls it slice 3 and the landing site for the recovered ETL class.

| Tool | Origin | Phase |
|---|---|---|
| `rates` — upsert keyed by `(series, obs_date)`, revision reporting | **BUILT** | — |
| `connect` — one entry point over sqlite / postgres / odbc | **NEW** | 3 |
| `infer_ddl` — column types from values | **NEW** *(see §9.5)* | 3 |
| `create_sql` / `to_table` | **NEW** *(see §9.5)* | 3 |
| `profile` — row counts, null rates, cardinality, min/max, inferred type | **NEW** | 3 |
| `bulk_load` — COPY / `fast_executemany` / executemany fallback | **NEW** | 3 |
| `schema_diff` — two schemas, what moved | **NEW** | 3 |
| `copy_table` — cross-engine move (the recovered ETL class, §12) | **NEW** | 3 |

## 7. `transform/`, `quality/`, `registry/`, `lineage/`, `cli/`

| Tool | Package | Origin | Phase |
|---|---|---|---|
| provenance-carrying row ops | `transform/` | **NEW** | 2 |
| `consolidate` — name normalisation, money/percent coercion, merge | `transform/` | **NEW** *(see §9.5)* | 4 |
| `check(frame, rules)` — validation rules as data | `quality/` | **NEW** | 9 |
| `reconcile(a, b, key)` — two-sided, with a break report | `quality/` | **NEW** | 9 |
| `drift` — PSI and friends | `quality/` | port:`scoring` | 9 |
| format/adapter catalogue | `registry/` | port:`finio_registry` | 2 |
| authority, revision, evidence date (axiom 11) | `registry/` | port:`finio_registry` | 2 |
| "may implement" vs "may redistribute" (axiom 12) | `registry/` | **NEW** | 2 |
| `LineageStore` — runs, datasets, fields, edges | `lineage/` | **BUILT** | — |
| SQL-level lineage: projection, predicates, derivations, `trace`, `impact` | `lineage/` | port:`discovery` | 7 |
| static-vs-observed edge reconciliation | `lineage/` | **NEW** | 7 |
| `rates`, `lineage` verbs | `cli/` | **BUILT** | — |
| `recognize`, `profile`, `copy`, `check` verbs | `cli/` | **NEW** | with each |

## 8. Domain and analysis

| Tool | Origin | Phase |
|---|---|---|
| `lending` — amortisation, events, payoff, LTV/DTI/DSCR | port:`lending` | 6 |
| `deposits` — tiered interest, certificates, maturity | port:`deposits` | 6 |
| `credit` — delinquency buckets, migration, roll rates, vintage | port:`credit` | 6 |
| `scoring` — WOE/IV, KS, AUC, scorecard scaling, PSI | port:`scoring` | 6 |
| `estate` | port:`estate` | 6 |
| `forensics` — Beneish, Piotroski, Altman, dilution | port:`forensics` **AGPL** | 8 |

---

## 9. What drawing the map exposed

Five things, none of which were visible from any single prior document:

1. **`quality/` is entirely NEW.** Four of the tools above have no gBASIC
   ancestor, and reconciliation with break reports is the one most likely to
   be asked for first by anyone doing this work for a living. It has never
   been designed here — §4 gives it eleven words.

2. **ISO 8583, SWIFT MT and X9.37 are NEW, not ports** (§4 above). The design
   doc groups them with NACHA. That grouping is wrong and would have been
   discovered mid-phase.

3. **`core/http` does not rate-limit**, though §7 of the design doc says the
   shared core "carries retry with backoff, an on-disk response cache, rate
   limiting, and a User-Agent policy." Three of four are true. EDGAR requires
   10 requests/second and Phase 8 depends on it, so this is a real gap with a
   known consumer — it is listed in Phase 0 above.

4. **The AGPL gate was in the wrong place.** `porting-plan.md` §4 says
   phases 0-7 are entirely Apache-2.0. They are not, as written: the `db/`
   slice needs `dbframe` at Phase 3 and `transform/` needs `consolidate` at
   Phase 4, and both are AGPL.

   **Recommended:** write those three fresh rather than port them. Combined
   they are 626 lines of column-type inference, `CREATE TABLE` emission and
   name/percent coercion — obvious logic with no hard-won behaviour in it,
   which is exactly the kind that is cheaper to write than to relicense. The
   gate then genuinely sits at Phase 8, where the code that *is* hard-won
   (EDGAR, `forensics`) lives. They are marked **NEW** above for this reason.

5. **Two incompatible layouts.** Design §4 puts everything in ten
   subpackages; the translation law requires `library dates` → `etools.dates`
   at top level, or the parity claim fails on the very first import a reader
   types. These cannot both hold.

   **Recommended:** the ten subpackages are the *ETL machinery*
   (`core` `formats` `adapters` `sources` `db` `transform` `quality`
   `registry` `lineage` `cli`); ported gBASIC libraries sit **alongside** them
   at top level, named exactly as in gBASIC. `etools.dates`, `etools.frame`,
   `etools.finance` — and `etools.db.profile`. This needs a ruling before
   Phase 1 writes the first import.

## 10. Counts

**61 rows.** 7 built, 29 ported, 4 shimmed, 21 new. Some rows cover several
libraries — one row is the five EDGAR analysis modules — so the row count runs
smaller than the module count in `porting-plan.md` §2.

Three rows carry the AGPL gate, all in Phase 8, once §9.4 is applied.

The 21 NEW ones are where the estimate is softest: a port has a working
implementation and a test suite to measure against, and a NEW tool has a
paragraph in a design document.
