# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""FRED series via the keyless CSV download endpoint.

No API key: ``fredgraph.csv`` is public. The official API at
``api.stlouisfed.org`` needs a free key, which buys nothing we need here.

**Send no User-Agent.** FRED silently drops requests carrying an unrecognized
one -- see :mod:`etools.core.http`.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from ..core import http
from ..core.run import current
from ._obs import Observation

NAMESPACE = "https://fred.stlouisfed.org"
CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def series(series_id: str, *, since: date | str | None = None,
           cache_ttl: float | None = 3600):
    """Observations for one FRED series, most recent last."""
    query = {"id": series_id}
    if since is not None:
        query["cosd"] = since.isoformat() if isinstance(since, date) else since
    url = f"{CSV_URL}?{urlencode(query)}"

    resp = http.get(url, user_agent=http.OMIT, cache_ttl=cache_ttl)

    out: list[Observation] = []
    for row in csv.DictReader(io.StringIO(resp.text())):
        text = row.get(series_id)
        if text in (None, "", "."):
            continue              # Axiom 7: a gap is not a bad value
        try:
            value = Decimal(text)
        except InvalidOperation:
            continue
        out.append(Observation(
            series_id,
            datetime.fromisoformat(row["observation_date"]).date(),
            value, NAMESPACE))

    r = current()
    if r is not None:
        r.input(NAMESPACE, f"series/{series_id}",
                fields=["observation_date", series_id], rows=len(out))
    return out


def latest(series_id: str, **kw) -> Observation | None:
    obs = series(series_id, **kw)
    return obs[-1] if obs else None
