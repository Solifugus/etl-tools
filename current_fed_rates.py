#!/usr/bin/env python3
"""Fetch the latest U.S. federal funds rates from FRED.

Uses public CSV downloads from the Federal Reserve Bank of St. Louis.
No API key or third-party Python packages are required.
"""

from __future__ import annotations

import csv
import io
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# FRED silently drops (RST_STREAM, no response) requests carrying an
# unrecognized User-Agent -- including browser-looking ones. urllib's default
# "Python-urllib/3.x" is accepted, so do NOT set a custom User-Agent here.

# Only fetch a recent window; the full history of a daily series is ~400 KB.
LOOKBACK_DAYS = 365


@dataclass(frozen=True)
class Observation:
    date: str
    rate: float


def _fetch(series_id: str, start: str | None) -> str:
    query = {"id": series_id}
    if start is not None:
        query["cosd"] = start
    with urlopen(f"{FRED_CSV_URL}?{urlencode(query)}", timeout=15) as response:
        return response.read().decode("utf-8-sig")


def _last_value(text: str, series_id: str) -> Observation | None:
    latest: Observation | None = None
    for row in csv.DictReader(io.StringIO(text)):
        value = row.get(series_id)
        if value not in (None, "", "."):
            latest = Observation(date=row["observation_date"], rate=float(value))
    return latest


def latest_observation(series_id: str) -> Observation:
    """Return the most recent non-missing observation for a FRED series."""
    start = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    latest = _last_value(_fetch(series_id, start), series_id)
    if latest is None:
        # Series may be discontinued or sparse; fall back to full history.
        latest = _last_value(_fetch(series_id, None), series_id)

    if latest is None:
        raise ValueError(f"FRED returned no observations for {series_id}")
    return latest


def main() -> int:
    try:
        lower = latest_observation("DFEDTARL")
        upper = latest_observation("DFEDTARU")
        effective = latest_observation("DFF")
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        print(f"Could not retrieve Fed rates: {error}", file=sys.stderr)
        return 1

    print(
        f"Federal funds target range: {lower.rate:.2f}%–{upper.rate:.2f}% "
        f"(effective {lower.date})"
    )
    print(
        f"Effective federal funds rate: {effective.rate:.2f}% "
        f"(observed {effective.date})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
