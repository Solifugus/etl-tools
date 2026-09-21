#!/usr/bin/env python3
"""Fetch 5- and 10-year Treasury yields and load them, showing what changed."""

from etools import run
from etools.db import rates
from etools.sources import treasury

db = rates.connect_sqlite("rates.db")

with run("daily-rates"):
    obs = treasury.yields(["DGS5", "DGS10"])
    report = rates.upsert_observations(db, obs)

print(f"observations : {len(obs)}")
print(f"inserted={report.inserted} revised={report.revised} "
      f"unchanged={report.unchanged}")
for series, day, old, new in report.revisions:
    print(f"  REVISED {series} {day}: {old} -> {new}")
