# Development roadmap — the library family

**Status:** Proposal (2026-09-23).\
**Path:** `docs/roadmap.md`\
**Supersedes the *scope* of** `docs/porting-plan.md`; that document's
translation law (§1.1) still governs **how** anything gets ported.\
**Companion:** `docs/tool-map.md` (inventory), `docs/etools-design.md`
(architecture).

---

## 1. The selection rule

> "build out new python libraries for them — unless there is already a strong
> contender for that need, among existing python libraries"

Applied literally, with two refinements that the survey forced:

**Per need, not per library.** A gBASIC library is not the unit of decision. A
need is. `xlsx` is one library and four needs, and the answer differs for each
one.

**Per layer, not per package.** `xlsx.c` is 6,514 lines across five layers.
openpyxl is a *strong* contender for layer 0 and has no answer at all for
layers 2 and 4. "Adopt openpyxl, build on top of it" is the right verdict and
is invisible if the question is asked at package granularity.

Three verdicts follow: **BUILD** (no contender), **ADOPT** (a strong contender
exists — use it, don't reimplement it), **ADOPT+BUILD** (a contender covers the
substrate; the distinctive layer goes on top).

Contenders named below should be **re-checked for health and license before
each wave commits**. This is an assessment from knowledge, not from PyPI today.

---

## 2. The verdicts

### 2.1 BUILD — nothing in Python does this

| Need | gBASIC | Closest Python thing | Why it does not cover the need |
|---|---|---|---|
| **Anchor-relative extraction from irregular text reports** | `ari` (2,230) | **TextFSM**, TTP, `parse`, pyparsing | TextFSM is the real contender and is a *different model*: a row-oriented state machine. ARI anchors on landmarks and **delimits by type** — "the last money-shaped token on this row". The fixture that forced it: `$6,000.25-` is one column wider than a positive because the trailing minus is appended after right-justification, so no fixed column and no heading can find the amount. Nothing in Python expresses that. |
| **Spec inference from a corpus of reports** | `ari_discover` (3,663, **unbuilt**) | *nothing* | Give it forty quarters of the same report and have it propose the ARI spec. No Python analogue exists at any maturity. |
| **Region extraction from irregular spreadsheets** | `xlsx.c` L2 | pandas `read_excel`, openpyxl | Both assume a rectangle. Real workbooks have several tables per sheet, headers that move between quarters, and subtotals interleaved with data. This is ARI generalised to a grid, over a *cleaner* substrate — a sheet is already typed. |
| **Excel formula → set-based operation / SQL** | `xlsx.c` L4 | **`formulas`**, **pycel**, koala2 | These are strong at *evaluating* a workbook, and all three build a **cell-by-cell calc graph** — the exact model `xlsx_design.md` §7 identifies as the reason Excel-over-big-data has repeatedly failed to scale. Compiling `SUMIF` to a filtered aggregate is a different target. |
| **Financial adapter framework with provenance** | `finio` family (6,159) | `ofxparse`, `sepaxml`, assorted thin NACHA readers | Format-by-format, no shared framework, no source retention, no recognition-with-evidence, no loss report. A parser that drops the unparsed remainder cannot answer "where did this value come from". |
| **ISO 8583 / SWIFT MT / X9.37** | *none — new here too* | sparse, mostly abandoned | Named in the design doc; no gBASIC ancestor either. Genuinely new work in both trees. |
| **Findings that carry their search width** | `reasoning`, `insight` (1,584) | statsmodels multiple-comparison corrections | The correction exists; the **discipline** does not. `insight` exists because a drill-down produced the same confident three-level causal chain from a real collapse and from pure noise, matching headlines to a tenth of a percent. A finding that cannot state its width is not a finding. |

### 2.2 ADOPT+BUILD — a contender covers the substrate

| Need | Adopt | Build on top |
|---|---|---|
| **xlsx read/write/round-trip** | **openpyxl** — adopted outright, never reimplemented | Nothing. The grid layer starts after a worksheet object exists. |
| **Excel formula evaluation** | **`formulas`** or **pycel** | Only the set-based compiler; do not reimplement evaluation |
| **SQL parsing and column lineage** | **sqlglot** (has a `lineage()`; excellent dialect coverage) | `discovery`'s governing split: **declared** (read from the catalog, certain) vs **inferred** (the result of a search, and therefore carrying its width, null model and threshold). At 10,000 columns there are ~50M candidate pairs and coincidence is a certainty, not a risk. sqlglot gives the parse; it has no opinion about that. |
| **Business calendars** | **workalendar**, **exchange_calendars** | Holiday data is solved. `dates`'s recurrence spec language (`series`, `matches`, business *hours*) is not. |
| **Fake data** | **Faker** | Names and addresses are the easy half. Build the distribution layer and **planted anomalies** — a population with a known defect in it is what tests `forensics`. |
| **Vector retrieval** | pgvector + your DB | Not a library at all — `retrieval`'s content is one rule: the permission predicate goes in the `WHERE`, never a post-filter, or a narrow user is silently told nothing matched. Write it down; it is a page, not a package. |

### 2.3 ADOPT — a strong contender; do not rebuild

`stats` → **scipy** + **statsmodels** · `matrix` → **numpy** · `xml` → **lxml**
· `ocr` → **pytesseract** (gBASIC shells to the same tesseract CLI) or docTR ·
`gpdf` → **reportlab** / **pdfplumber** · `chart` → **altair** (a Vega-Lite spec
is deterministic JSON, so the golden-file testability survives) · `crypto`,
`otp` → **hashlib**, **cryptography**, **pyotp** · `web`, `mail` → **httpx**,
stdlib · `llm`, `mcp`, `agent` → the **anthropic** SDK and the **MCP Python
SDK** · `ldap` → **python-ldap**.

### 2.4 SKIP — language- or GUI-bound

`gui` `gtk` `gtkui` `gtksourceview` `sourceeditor` `datagrid` `grid`
`rowmodel` `filetree` `tools`, and the gBASIC-specific `notation` (TOML covers
most of it; money and duration are the only real gaps, and they are not worth a
serialization format).

---

## 3. The shape: one family, not one library

The survey changes the packaging question, because two of the BUILD items have
an audience far wider than fintech ETL:

| Package | Contains | Audience |
|---|---|---|
| **`etools`** | The ETL spine: sources, db, lineage, quality, transform, registry | This project |
| **`ari`** *(name to be checked)* | Anchor-relative extraction + spec inference | **Anyone parsing legacy reports.** Banking, insurance, healthcare, telecom billing, government. Does not mention finance anywhere. |
| **`etools.sheets`** | The xlsx L2-L4 stack over openpyxl | Fintech, CECL tapes, anyone consolidating workbooks |
| **`finio`** *(inside `etools` at first)* | Adapter framework + payment formats | Payments |

> **Superseded by `docs/packaging.md` (2026-09-23).** The one-distribution
> recommendation below did not survive the audience test: the family is **five**
> distributions, ARI is zero-dependency in its own repo, and the xlsx layers
> split across three of them. Read that document instead of this section.

---

## 4. The roadmap

Five waves. Each ends with something usable on its own; nothing is scheduled
that has no consumer.

### Wave 0 — Foundations *(unchanged from `porting-plan.md` Phase 0-1)*

`UNKNOWN` / `Outcome` / `LossReport`, `money`, HTTP rate limiting, the parity
harness, then `dates` over workalendar and `persist`.

**Ends with:** the value layer every later wave returns.

**COMPLETE 2026-09-24.** `tervalue` holds the four kernel types with 33
tests; the parity harness runs in both trees; `dates` is ported into
`etools.dates`, adopting stdlib `date`/`datetime`/`timedelta` for the value
kinds and workalendar for holiday data behind the `calendars` extra; and
`etools.persist` gives atomic writes and a read that reports missing, corrupt
or loaded as a value rather than raising.

92 unit tests and 128 parity cases; both trees green. `arispec` and `finio`
are reserved on PyPI.

The port found **four** upstream gBASIC defects — one in `money`, two in
`dates`, one in `persist` — which is the return on building the harness
before the libraries it checks rather than after. See `parity/README.md`.

Wave 1 (ARI) is next.

### Wave 1 — ARI *(the distinctive bet)*

Promoted from "skip" to first substantive wave, because it is the item with the
widest gap between its value and its Python competition.

- ARI spec parser and runtime: anchors (direction, distance, pattern),
  `as <type>` **delimiting** rather than converting, page furniture, form feeds.
- `inspect` / `trace` — span-level claimed vs unclaimed, so a spec that quietly
  stops matching is visible.
- Emits a frame. Fixtures: gBASIC's `examples/fixtures/ari/`.
- **Then** `ari_discover` — inference from a corpus. gBASIC has the design and
  no implementation, so this would ship **in Python first**. That is a
  departure from parity and it is the right one; feed the result back.

**Ends with:** a standalone library that turns legacy print reports into
frames. Independently useful, independently publishable.

**Status 2026-09-24 — the parser, the runtime and `trace` are built.**
`packages/arispec/`, 0.1.0, **zero dependencies**. Verified against all three
gBASIC fixtures and their golden files: `teller_totals.rpt` (irregularity),
`teller_totals_generated.rpt` (form feeds, three money dialects in one file),
`delinquency.rpt` (vertical locators, varying gaps, wrapped rows, refused
ambiguous dates). Output is identical to gBASIC's, line for line, including
line counts. 58 tests.

Built: page furniture (form feeds and header patterns), the indented spec
language, all eight locators with exact/range/open/flush distances, `as <type>`
**delimiting**, custom types with ordered rules and `/re/repl/` transforms,
`using` bindings with lexical scope and dialects, `repeats`/`starts`/`ends`,
`rows:` with `continue(...)`, and `trace` with claims, unclaimed runs,
coverage and collisions.

One platform divergence, handled rather than inherited: a spec writes `$1`..`$9`
group references in a `/re/repl/` transform, because that is gBASIC's
`replace()` spelling and one spec file must read the same in both trees. Python's
`re.sub` wants `\1`, and handed the spec's own spelling would silently emit the
literal string `$3-$2-$1`. Translated inside the engine, not in the spec.

Not yet built: `ari_discover`.

### Wave 2 — `arispec.grid`

**openpyxl is adopted outright and never reimplemented** — it is already the
tool of choice here, and the grid layer starts after a worksheet object exists.
See `packaging.md` §4.

- `grid.from_openpyxl` / `from_csv` / `from_rows` — adapters, not readers.
- Region extraction over an irregular grid, reusing Wave 1's spec engine.
  *This is why ARI comes first.*
- L3 consolidation — column aliasing, unit normalisation, merge — lands in
  `etools.transform`, not here.
- Evaluate `formulas`/pycel and adopt one. The set-op compiler is deferred to
  Wave 5; it is the most speculative item in the document.

**Ends with:** messy workbooks → clean frames → database tables.

### Wave 3 — finio and the payment formats

Unchanged from `porting-plan.md` Phases 2-3: framework and NACHA together,
then BAI2, OFX, CAMT, PAIN001. ISO 8583 / SWIFT MT / X9.37 are new work and are
sized separately, not folded in.

### Wave 4 — The ETL spine completed

`frame`, `fake` over Faker, `db.profile` / `bulk_load` / `schema_diff` /
`copy_table`, `quality.check` / `reconcile` / `breaks`, and `discovery` over
**sqlglot** reconciled against the run-time lineage already recorded.

**Ends with:** what `etools-design.md` originally promised.

### Wave 5 — Domain and the speculative

`finance`, `accounting`, `lending`, `deposits`, `credit`, `scoring`; the
formula→set-op compiler; `insight`/`reasoning` if they have earned a consumer
by then. The AGPL gate (`porting-plan.md` §4) applies to EDGAR here.

---

## 5. What this changes

Three reversals, all in the same direction — I under-rated the distinctive work
because I was asking "does Python have a library called this?" instead of "does
Python answer this need?":

1. **`ari` moved from SKIP to Wave 1.** I filed it under the AI layer. It is
   not an AI library; it is a declarative extraction language for irregular
   text, and it is the strongest single idea in the tree for this project.
2. **`xlsx` moved from SHIM to a wave of its own.** "Shim to openpyxl" is
   right for one of its five layers and wrong for the rest. A formula engine,
   dependency-ordered recalc, grid extraction and a set-op compiler are not a
   shim.
3. **`discovery` and `dates` moved from PORT to ADOPT+BUILD.** sqlglot and
   workalendar are strong and were not named in either earlier document.

The line-count estimates in `porting-plan.md` §6 are now **too high** — adopting
scipy, openpyxl, sqlglot, workalendar and Faker removes more than porting ARI
and the sheets stack adds — but the *calendar* is longer, because Waves 1 and 2
are design work, not translation.

---

## 6. Open decisions

1. **Is `ari` a separate distribution from day one?** §3 says separate package,
   one distribution. The alternative is publishing it standalone immediately,
   which buys an audience and costs a release process.
2. **Name for ARI on PyPI.** `ari` is short and probably taken; check
   `arispec`, `anchorspec`, `ari-extract` before Wave 1 writes an import.
3. **Does `dates` leave `etools`?** Deferred in `packaging.md` §10 and still
   deferred, but the shape is now visible: `etools.dates` imports nothing from
   the rest of `etools` and only `UNKNOWN` from the kernel. It is a sixth
   distribution the day somebody asks for it and not before.
4. **Does `ari_discover` really ship in Python first?** §4 Wave 1 says yes.
   It is the first deliberate break from "gBASIC leads, Python follows", and
   worth confirming rather than drifting into.
5. **`formulas` vs `pycel`** — evaluate in Wave 2 against a real workbook, not
   from documentation.
6. **Does `insight`/`reasoning` belong in an ETL library at all?** Wave 5 is a
   placeholder. The idea is strong; the fit is unproven.
