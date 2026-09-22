# ETools

ETL tools with first-class provenance, and financial data retrieval.
Design: [`docs/etools-design.md`](docs/etools-design.md).

Stdlib-only core. Postgres, ODBC, xlsx and dataframe interop live behind
extras that fail with an install message naming the extra.

## Daily Treasury yields

```bash
python -m etools rates --sqlite rates.db                    # no install needed
python -m etools rates --postgres postgresql:///etools_rates --cross-check
python -m etools lineage
```

Or as a library:

```python
from etools import run
from etools.db import rates
from etools.sources import treasury

db = rates.connect_postgres("postgresql:///etools_rates")
with run("daily-rates"):
    obs = treasury.yields(["DGS5", "DGS10"])
    report = rates.upsert_observations(db, obs)

print(report.inserted, report.revised, report.unchanged)
for series, day, old, new in report.revisions:
    print(f"{series} {day}: {old} -> {new}")
```

Nothing in that snippet mentions lineage. It is recorded anyway, by the
ambient run context, into `.etools/lineage.db`.

## Two things worth knowing

**No API key, and nothing to pay.** Treasury's yield-curve feed and FRED's
`fredgraph.csv` are both public and keyless. FRED's official API at
`api.stlouisfed.org` needs a free key and buys nothing we need.

**The two sources have opposite User-Agent filters.** FRED silently drops
requests with an unrecognized or browser-shaped UA and accepts urllib's
default. Treasury does the exact reverse. Neither fails cleanly -- both accept
the connection and then send nothing until the read times out. So the UA is a
per-source policy, in `etools/core/http.py`, not a transport default.

## The table is an upsert

These series get revised. The table is keyed by `(series, obs_date)` and the
load reports `inserted` / `revised` / `unchanged` separately, so a restatement
is visible rather than silently overwritten.

## Running it daily

```bash
./deploy/systemd/install.sh postgresql:///etools_rates .venv/bin/etools
```

Installs a **user** timer -- no root, no system units -- that fires weekdays at
18:30 local, after Treasury posts the day's curve. `Persistent=true` means a
day missed to a powered-off machine runs at the next boot rather than being
skipped. Check on it with:

```bash
systemctl --user list-timers etools-rates.timer
journalctl --user -u etools-rates.service -n 50
```

A load that cannot reach either source, or cannot reach the database, exits
non-zero and lands in the journal as one line. Note that an *empty* result is
treated as a failure too: an empty upsert succeeds and reports zero rows, which
is exactly what a silent breakage looks like when nobody is reading the output.

## Tests

```bash
python -m unittest discover -s tests
```

No test performs network access.
