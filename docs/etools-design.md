# ETools — design

**Status:** Skeleton (2026-09-21). Nothing built. Every section below is a
*proposal* until marked otherwise.\
**Path:** `docs/etools-design.md`\
**Library name:** `etools` ("oo" added for the excitement — ETooL ≈ ETL)\
**Scope:** General-purpose ETL for business data, with first-class provenance,
plus retrieval adapters for financial-services sources and formats.

**Supersedes:** `~/development/ETooLs/design.md`, recovered 2026-09-21 from a
stale Kate swap file (the on-disk copy was zero bytes). That draft is §12 here.

---

## 1. Purpose

A suite of importable Python modules — with thin CLI wrappers — for the work
data programmer/analysts actually do: pull data from somewhere, understand its
shape, move it somewhere else, and be able to say afterwards where every value
came from.

Financial services first, because that is where the formats are hardest and
the provenance requirements are real. Not limited to it.

## 2. What this is not

- Not a pipeline scheduler. Cron, systemd timers and Airflow exist.
- Not a dataframe library. Optional interop, never a hard dependency.
- Not a replacement for SQLSplicer (interactive DB work, exports).
- Not a BI tool. gdash covers dashboards.

## 3. Axioms

Adopted from gBASIC's `finio` framework
(`~/development/gbasic/docs/financial_adapters_design.md` §2). They earned
their place there; they are not re-derived here.

| # | Axiom | Consequence for ETools |
|---|---|---|
| 1 | Preserve the source | Unparsed remainder is retained, never dropped |
| 2 | Every interpretation has provenance | §5 |
| 3 | Meaning ≠ representation | `formats/` (bytes) split from `adapters/` (meaning) |
| 4 | History is immutable | Adapter revisions are additive and kept indefinitely |
| 5 | Evolution is data, not API | New formats = new registry rows, not new functions |
| 6 | Never silently guess | Recognition returns candidates + evidence, or ambiguity |
| 7 | Unknown ≠ invalid | Three-valued results: ok / unknown / invalid |
| 8 | Loss must be explicit | Lossy transforms return a loss report |
| 9 | Parsing ≠ policy | Severity and routing belong to the caller |
| 10 | Recognition is a capability | `etools.recognize(path)` over unknown files |
| 11 | Adapters have provenance | Registry records authority, revision, evidence date |
| 12 | Legal availability matters | Registry distinguishes "may implement" from "may redistribute" |

## 4. Package layout

> The consolidated inventory of what goes in each of these — 61 tools, with
> origin and phase — is `docs/tool-map.md`. It also records two corrections to
> this section: `quality/` is entirely unbuilt and undesigned, and ported
> gBASIC libraries sit at top level beside these subpackages rather than
> inside them (`tool-map.md` §9.5).


```
etools/
  core/        values, three-valued results, loss reports, retry, cache, rate limits
  lineage/     the provenance graph: record, query, export
  formats/     representation: fixedwidth, delimited, xml, json, edi, xlsx
  adapters/    meaning: nacha, iso8583, swift_mt, x937, ofx, …
  sources/     network retrieval: fred, treasury, edgar, fdic, ffiec
  db/          odbc, postgres, sqlite: profile, infer DDL, bulk load, schema diff
  transform/   typed row operations that carry provenance through
  quality/     validation rules, reconciliation, break reports
  registry/    format/adapter catalogue (§3 axioms 11–12)
  cli/         thin `python -m etools <verb>` wrappers
```

## 5. The provenance model — **DECIDED 2026-09-21**

**Side-car always; per-cell opt-in per adapter.** Dataset/column lineage is
cheap enough to be unconditional. Byte-level provenance is switched on for the
adapters where someone may actually ask, and off for bulk movement. Row-level
granularity is rejected: it costs most of per-cell and answers much less.

### 5.1 The side-car graph (always on)

Four node kinds, deliberately the OpenLineage shape so the graph can be
exported to Marquez or anything else that speaks it:

| Node | Identity |
|---|---|
| `Run` | one execution — id, job name, started, finished, status, code version |
| `Dataset` | namespaced name: `postgres://host:5432/db.schema.table`, `file:///path`, `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF` |
| `Field` | a column within a Dataset |
| `Edge` | Dataset → Dataset, carrying the field-level mapping and the transform that produced it |

**Recording must not be the caller's job.** If lineage requires bookkeeping at
every call site it will be wrong within a month. A `Run` is an ambient context
(a `contextvar`); sources and sinks register themselves as they are used:

```python
from etools import run
from etools.sources import fred
from etools import transform, db

with run("daily-rates") as r:
    obs  = fred.series("DFF", since="2026-01-01")   # registers an input Dataset
    rows = transform.rename(obs, {"DFF": "eff_rate"})  # registers an Edge
    db.load(rows, conn, "rates.daily")              # registers an output Dataset
```

Nothing above mentions lineage. That is the design.

**Storage is `sqlite3`** — stdlib, so the always-on path adds no dependency.
Default `./.etools/lineage.db`, overridable. Export to OpenLineage JSON.

### 5.2 Per-cell provenance (opt-in)

Enabled per call, by the adapters that need it:

```python
batch = adapters.nacha.read(f, provenance="cell")
```

**Not a wrapper type.** A `SourceValue` object boxing every cell poisons
everything downstream — arithmetic needs unwrapping, `json.dumps` breaks,
every consumer learns about provenance whether it wanted to or not. Instead
values stay plain Python and refs live in a **parallel sparse map** keyed by
position:

```python
rows[3]["amount"]            # Decimal("1250.00")  — an ordinary value
prov(rows)[3]["amount"]      # SourceRef(...)
```

```
SourceRef(
    dataset,      # which source
    record,       # record index within it
    field_path,   # "batch[2].entry[17].amount"
    span,         # byte range, or None where the representation has no offsets
    rule,         # the adapter rule that produced it -> Axiom 11
)
```

`span` is `None` rather than fabricated for representations without byte
offsets (Axiom 6: never silently guess). Per-cell refs **roll up** into
field-level Edges in §5.1 automatically, so turning the flag on enriches the
side-car rather than producing a second, disconnected record.

### 5.3 What rides alongside

Two axioms need a channel and this is it:

- **Axiom 7** — results are three-valued: `ok` / `unknown` / `invalid`. A blank
  field and a broken field are different answers.
- **Axiom 8** — any lossy transform returns a loss report naming what it could
  not preserve. Lossy is permitted; silent is not.

### 5.4 Open sub-questions

- Does `Run` survive process death mid-pipeline, or is a crashed run simply
  left `started` with no `finished`? (Proposal: the latter — it is honest.)
- Do we emit OpenLineage events live over HTTP, or only export on demand?
  (Proposal: export on demand; live emission is a `[lineage-http]` extra.)

## 6. Dependency policy — **DECIDED 2026-09-21**

Stdlib-only core; everything else behind extras that fail with an install
message naming the extra.

```
pip install etools              # csv, json, urllib, sqlite3, decimal, struct
pip install etools[odbc]        # + pyodbc
pip install etools[postgres]    # + psycopg
pip install etools[frames]      # + polars  (interop only)
pip install etools[xlsx]        # + openpyxl
```

Rationale inherited from `sqlite_design.md`: "keep the module optional so
gBASIC still builds without sqlite3 development files."

## 7. Slice 1 — financial data sources — **DECIDED 2026-09-21**

Generalize `current_fed_rates.py` into a connector family over a shared core.

| Source | First call |
|---|---|
| FRED | `fred.series("DFF", since=…)` |
| Treasury | `treasury.yield_curve(date)` |
| SEC EDGAR | `edgar.facts(cik)` — port from gBASIC `stdlib/edgar.bas` |
| FDIC / FFIEC | `fdic.call_report(cert, quarter)` |

Shared core carries: retry with backoff, on-disk response cache, rate limiting,
and a **User-Agent policy**. The last is not incidental — FRED silently drops
requests with unrecognized User-Agents (RST_STREAM, no response, hangs until
timeout). Discovered 2026-09-21; see §12 of this repo's history.

## 8. Later slices

2. Financial file formats (`adapters/`) — NACHA, fixed-width, ISO 8583, SWIFT MT
3. DB movement + profiling (`db/`) — this is where §12's recovered `ETL` class lands
4. Reconciliation + quality (`quality/`)

## 9. Testing method

Adopt gBASIC's "**this page cannot lie**" convention (`odbc_cookbook.md`):
the cookbook owns neither the code nor the output. `examples/NN_name.py` owns
the code, `examples/NN_name.out` owns the output, a sync script copies both
into the docs, and the test suite fails while any of them disagree.

Corollary from the same doc: **a recipe that works against SQLite is not
thereby portable.** DB adapters get tested against real engines or are marked
unverified.

## 10. Name and distribution — **DECIDED 2026-09-21**

Measured 2026-09-21:

| Name | PyPI | Notes |
|---|---|---|
| `etools` | **taken** | v0.0.16, "some useful tools", last release 2020-06-29 |
| `etool` | taken | active, office automation CLI |
| `etl-tools` | taken | single release, 2019 |
| `etools-etl` | free | |
| `etools-lib` | free | |
| `etools-py` | free | |

`github.com/Solifugus/etools` is free.

Three independent names, and only the first is the one you see day to day:

| Role | Name | Why |
|---|---|---|
| Repo / folder | **`etl-tools`** | Unmistakable in a listing of 156 directories. Free at `github.com/Solifugus/etl-tools` — the PyPI collision does not reach it. |
| Import | **`etools`** | Short to type; keeps the "oo" joke. |
| Distribution | **`etools-etl`** | Set in `pyproject.toml`. Only matters if published. |

Repo name ≠ import name is ordinary, not a compromise: `scikit-learn`/`sklearn`,
`beautifulsoup4`/`bs4`, `python-dateutil`/`dateutil`, `pillow`/`PIL`.
Descriptive outside, short inside.

A PEP 541 transfer request for the abandoned `etools` on PyPI is cheap to file
and unlikely to succeed quickly. Not worth waiting on.

## 11. Open decisions

> Decisions 1-3 are answered in `docs/porting-plan.md` §7, which also carries
> the roadmap for porting gBASIC's libraries into this tree. They are left
> stated here because that plan is still a proposal.


1. **One distribution or several?** `etools` vs `etools-core` + `etools-fin`.
2. **Does the `db/` layer target T-SQL first** (as §12 does) **or Postgres**
   (as Nexordia does)?
3. Python floor — 3.11? 3.12? Affects `tomllib`, f-string rules, `Self`.

## 12. Recovered prior art

`~/development/ETooLs/design.md`, 2026-02-01. A single `ETL` class over
**pyodbc**: named connection registry, `run_sql`/`fetch`, a nested `SqlBuilder`
that rewrites `@name` params to positional `?` plus a debug-SQL preview,
`INFORMATION_SCHEMA` introspection, `CREATE`/`ALTER` generation, type inference
with width bucketing, and list-of-dicts ↔ dict-of-lists conversion.

T-SQL flavored. Lands in `db/` and `core/` at slice 3. Known defects in the
draft: `_infer_type` tests `all_int` before `all_bool` and `bool` subclasses
`int`, so a boolean column can never infer `BIT`; an all-`None` column raises
on `max()` of an empty sequence; `format_val`'s quote escape is a pre-3.12
f-string syntax error.
