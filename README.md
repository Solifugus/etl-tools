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

## Business calendars and recurrence

`etools.dates` is a port of gBASIC's `stdlib/dates.bas`, so learning one
teaches the other: same function names, same argument order, same error text.

```python
from datetime import timedelta
from etools.dates import calendar, select, series, add_business_hours

cal = calendar(holidays=["2026-12-25"], hours={"open": "9:00", "close": "17:00"})

select({"nth": 3, "weekday": "thursday", "within": "month"}, "2026-08-17")
# date(2026, 8, 20)

series({"every": "month", "when": {"nth": 3, "weekday": "thursday"}, "at": "14:00"},
       {"from": "2026-01-01", "through": "2026-06-30"}, cal)
# six board meetings, each stamped 14:00

series({"every": timedelta(weeks=2), "roll": "backward"},
       {"from": "2026-01-02", "count": 26}, cal)
# a year of paydays, none of them on a holiday

add_business_hours("2026-12-24 15:00", timedelta(hours=4), cal)
# datetime(2026, 12, 28, 11, 0) -- the holiday and the weekend paused the clock
```

One vocabulary, three verbs: `matches` asks, `select` finds the one day (or
`UNKNOWN`), `series` enumerates. A **spec is a dict** and stays one, because
recurrence rules live in databases and config files, not in source.

Three things are adopted rather than built. The datetime kind is stdlib
`date`/`datetime`; exact durations are `timedelta`; and holiday **data** is
workalendar, behind `pip install etools-etl[calendars]` and an explicit
conversion:

```python
from workalendar.usa import UnitedStates
from etools.dates import holidays

cal = holidays.from_workalendar(UnitedStates, range(2026, 2029))
```

No holiday pack ships here by default, on purpose. Observed-versus-actual
rules differ per employer inside one country; packs rot silently, and a
holiday moved by decree becomes a wrong `is_business_day` with no error
anywhere. A wrong holiday from your data is your data bug; a wrong holiday
from a pack we shipped would be ours, forever.

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
