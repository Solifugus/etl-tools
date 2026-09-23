# The library family — how this breaks up

**Status:** Proposal (2026-09-23). One decision in §8 is urgent; the rest can wait.\
**Path:** `docs/packaging.md`\
**Companion:** `docs/roadmap.md` (what gets built), `docs/tool-map.md` (inventory).

---

## 1. The test

A separate distribution is justified when **someone would install one without
wanting the other**. Not "is this a different topic" — topics are free, and
splitting by topic produces five installs for one job.

Applied:

| Would they? | |
|---|---|
| ARI without the ETL spine | **Yes.** An insurance analyst parsing legacy print reports wants nothing else here. |
| finio without the ETL spine | **Yes.** A payments shop reading NACHA and BAI2. |
| The ETL spine without finio | **Yes.** Pulling FRED into Postgres touches no payment format. |
| Retail-banking math without any of it | **Yes.** A loan calculator needs amortisation, not a lineage graph. |
| The value kernel alone | No — but it is infrastructure, and that is the point. |

Five pass. Five distributions.

---

## 2. The family

| Distribution | Import | Depends on | Audience |
|---|---|---|---|
| **kernel** *(§7)* | `etcore` | — | Everything below |
| **`arispec`** ⭐ | `arispec` | **nothing** | Anyone parsing irregular reports: banking, insurance, healthcare, telecom billing, government |
| **`finio`** | `finio` | kernel | Payments engineers |
| **`etools-etl`** | `etools` | kernel; `[ari]` `[finio]` `[postgres]` … | ETL engineers in financial services |
| **retail-banking math** *(§7)* | `finprims` | kernel | Fintech product developers |
| *(later)* formula compiler | — | — | Speculative; Wave 5 |

```
                    etcore  (kernel: UNKNOWN, Outcome, LossReport, Money, SourceRef)
                   /   |   \
              finio  etools  finprims
                       |
                    [extras] ──▶ arispec, finio, psycopg, openpyxl, sqlglot …

       arispec ── depends on nothing at all
```

**`etools` is the integration point, and it is the only one.** It may import
any of the others behind an extra; none of them may import it. That keeps the
graph acyclic without anyone having to think about it.

---

## 3. ARI pays for its independence, deliberately

`arispec` depends on **nothing** — not even the kernel. That means it defines
its own three-valued result and its own source span, duplicating about 150
lines of `etcore`.

That duplication is bought on purpose. ARI's audience is people inside
locked-down enterprise environments where every added dependency is a
procurement conversation, and "`pip install arispec`, nothing else, pure
Python" is a feature for them in a way it is not for anyone else here. The
kernel ships a documented ~10-line adapter that lifts ARI results into
`Outcome`, and `etools[ari]` is where that adapter lives.

The risk is real and worth stating: **two three-valued types that can drift.**
The mitigation is that `etcore`'s is the one that must not change (§6), and a
parity case in both trees covers the adapter.

---

## 4. The grid layer — and what it is not

**openpyxl is not reimplemented, wrapped, or competed with.** It reads and
writes `.xlsx`, it does that well, and nothing here touches that job. What we
build starts *after* a worksheet object already exists.

That settles the name too. The thing we build is **not a spreadsheet library**,
so it must not be named after a file format: the substrate is any 2D typed
grid — an openpyxl worksheet, a CSV, a database result, a pasted range — and
`xlsx` would be both narrower than the truth and an implied claim to openpyxl's
territory. It is **`arispec.grid`**.

```python
import openpyxl, arispec.grid as grid          # openpyxl does the file

ws     = openpyxl.load_workbook("tape.xlsx")["Q3"]
sheet  = grid.from_openpyxl(ws)                # a one-line adapter, no parsing
tables = grid.find(sheet, spec)                # ← the part that does not exist
```

`grid.from_openpyxl`, `grid.from_csv` and `grid.from_rows` are adapters, not
readers. They are a few lines each and hold no format knowledge.

The five layers of gBASIC's `xlsx.c` therefore land in four different places:

| Layer | Goes to | Why |
|---|---|---|
| L0/L1 — ZIP, XML, read/write, round-trip | **openpyxl** | Not ours. Never was. |
| L2 — region extraction from irregular grids | **`arispec.grid`** | It *is* ARI, over a cleaner substrate — a grid is already typed. Same spec language, second backend. |
| L3 — consolidation, column aliasing, unit normalisation | **`etools.transform`** | ETL, not extraction. |
| L4 — formula → set-op / SQL compiler | **its own dist, later** | The most speculative item in the roadmap; bolted to nothing that has to ship. |

**One spec language, two substrates — text and grid.** That is a better
library than either half, and it is why L2 belongs to the star rather than to
a spreadsheet package of its own.

If `arispec.grid` ever earns its own distribution, **`regionspec`** is free and
accurate. `gridspec` is also free and should be avoided — `matplotlib.gridspec`
means something else to exactly the people this is for.

## 5. Repos

**`arispec` gets its own repo from day one.** For a library meant to be found,
the repo *is* the pitch, and `github.com/Solifugus/etl-tools` does not say ARI.
It has no dependency on this tree (§3), so it loses nothing by leaving.

**Everything else stays in `etl-tools` as a monorepo:**

```
etl-tools/
  packages/
    etcore/      pyproject.toml + etcore/
    finio/       pyproject.toml + finio/
    etools/      pyproject.toml + etools/      ← today's code, unmoved
    finprims/    pyproject.toml + finprims/
```

Three distributions that share a kernel will churn that kernel early, and a
monorepo makes those changes one commit and one test run instead of three
coordinated releases. Extract any of them later if it earns an audience —
`git filter-repo` keeps the history, and it is cheap before a package has
issues and stars pointing at it.

---

## 6. Versioning

Each distribution versions independently. Dependencies are declared with a
**floor and a major ceiling** (`etcore>=0.3,<1`), never pinned.

The discipline that makes a shared kernel safe: **`etcore` reaches 1.0 quickly
and then stops changing.** A kernel that keeps moving forces a version matrix
on everything above it. If it is still churning at Wave 3, that is evidence the
split was wrong, not that the kernel needs another release.

---

## 7. Names — checked against PyPI today

| Role | Recommended | Free? | Alternatives (all free) |
|---|---|---|---|
| ARI | **`arispec`** | ✅ | `anchorspec`, `ari-spec`, `arikit`, `anchored` |
| Payments | **`finio`** | ✅ | — |
| ETL spine | **`etools-etl`** | ✅ *(already ours)* | — |
| Kernel | **`etools-core`** | ✅ | `provkit`, `sourcekit`, `tervalue` |
| Banking math | **`finprims`** | ✅ | `retailbank`, `bankprims`, `ledgerprims` |

Two notes on ARI's name. `ari` itself is **taken** — an Asterisk REST Interface
client, 0.1.3, long dormant — so the import name should be `arispec` too, not
`ari`. Anyone who wants the short spelling writes `import arispec as ari`, and
nobody's environment breaks. Taking the import name would be a small, avoidable
act of collision.

`finio` being free is worth acting on. It is your coined name, it is available,
and it will not stay available indefinitely.

---

## 8. What is urgent, and what is not

**Urgent — Wave 0 hits it immediately.** The kernel is the first thing Wave 0
builds (`UNKNOWN`, `Outcome`, `LossReport`, `Money`). Whether it is a separate
distribution or a module inside `etools` has to be settled *before* that code
is written, because the whole family's dependency graph hangs off it.

**Not urgent.** Nothing moves today. `etools` keeps every line it has; the
splits happen as the waves build, not as a refactor. `finprims` does not exist
until Wave 5. The formula compiler may never exist.

**Worth doing this week regardless:** reserve `arispec` and `finio` on PyPI
with a placeholder. Free names do not stay free, and both are load-bearing.

---

## 9. Open decisions

1. **Is the kernel a distribution?** §2 says yes. The alternative is folding it
   into `finio` — where the axioms were actually invented — and having `etools`
   depend on `finio`. That is defensible and slightly odd: an ETL library
   depending on a payments library. **Needed before Wave 0 writes a line.**
2. **Does ARI really carry its own duplicate value types?** §3 says yes, for
   its audience. Reversing this later is a breaking change for ARI's users.
3. **Name for the kernel.** `etools-core` is boring and unambiguous; `provkit`
   says what it holds. Boring is probably right for infrastructure.
4. **Does `dates` stay inside `etools`?** Business calendars have a wide
   audience and no dependency on anything here. It is a sixth distribution
   waiting to happen; leave it inside until it asks to leave.
