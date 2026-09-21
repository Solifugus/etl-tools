"""Slice 1's worked example: 5- and 10-year Treasury yields, loaded daily.

Treasury is primary because it publishes first -- FRED republishes the same
numbers about a day later. FRED is the fallback when Treasury cannot be
reached, and the cross-check when both are available.
"""

from __future__ import annotations

from datetime import date

from ..core.http import FetchError
from ..core.run import run
from ..db import rates
from ..sources import fred, treasury

SERIES = ("DGS5", "DGS10")


def fetch(series=SERIES, *, year: int | None = None, cache_ttl: float | None = 3600):
    """Treasury first; FRED on failure. Returns (observations, which_source)."""
    try:
        obs = treasury.yields(series, year=year, cache_ttl=cache_ttl)
        if obs:
            return obs, "treasury"
    except (FetchError, OSError) as e:
        print(f"  treasury unavailable ({e}); falling back to FRED")

    since = date(year or date.today().year, 1, 1)
    obs = []
    for s in series:
        obs.extend(fred.series(s, since=since, cache_ttl=cache_ttl))
    return obs, "fred"


def cross_check(observations, series=SERIES, *, cache_ttl: float | None = 3600):
    """Compare the loaded values against FRED. Returns disagreeing rows."""
    have = {(o.series, o.obs_date): o.value for o in observations}
    out = []
    for s in series:
        for o in fred.series(s, since=date(date.today().year, 1, 1),
                             cache_ttl=cache_ttl):
            mine = have.get((o.series, o.obs_date))
            if mine is not None and mine != o.value:
                out.append((o.series, o.obs_date, mine, o.value))
    return out


def load(db, *, series=SERIES, year: int | None = None, job: str = "daily-rates",
         lineage_db=None, cache_ttl: float | None = 3600):
    """The whole pipeline, inside one lineage run."""
    kw = {"db": lineage_db} if lineage_db else {}
    with run(job, **kw):
        observations, origin = fetch(series, year=year, cache_ttl=cache_ttl)
        report = rates.upsert_observations(db, observations)
    return observations, origin, report
