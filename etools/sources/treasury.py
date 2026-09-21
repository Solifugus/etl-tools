"""Daily Treasury par yield curve, straight from Treasury. No API key.

Treasury publishes a year of the curve as an Atom/XML feed. FRED republishes
the same numbers roughly a day later, so this is the primary and
:mod:`etools.sources.fred` is the cross-check.

Series ids are FRED's (``DGS5``, ``DGS10``) because that is the vocabulary the
caller already uses; the mapping to Treasury's own field names is below.

**On the User-Agent.** This feed sits behind a bot filter that drops urllib's
default, ``curl/*``, ``python-requests/*`` and any descriptive client string --
the connection is accepted and then nothing comes back until the read times
out. Only a browser-shaped User-Agent is served. This is the exact mirror of
FRED, which drops browser UAs and accepts urllib's default, and it is why the
User-Agent is a per-source policy rather than a transport default.

Treasury publishes no machine API for the par yield curve: the
``fiscaldata.treasury.gov`` service returns 404 for it and carries only the
monthly ``avg_interest_rates`` dataset. So there is no key-free, filter-free
route to this data. If you would rather not send a browser string, set
``user_agent=`` to something else and the fetch will fail over to FRED, which
carries the same numbers about a day later.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ..core import http
from ..core.run import current
from ._obs import Observation

NAMESPACE = "https://home.treasury.gov/resource-center/data-chart-center"

FEED = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates"
    "/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value={year}"
)

#: canonical series id -> Treasury's field name in the feed
FIELDS = {
    "DGS1MO": "BC_1MONTH", "DGS3MO": "BC_3MONTH", "DGS6MO": "BC_6MONTH",
    "DGS1": "BC_1YEAR", "DGS2": "BC_2YEAR", "DGS3": "BC_3YEAR",
    "DGS5": "BC_5YEAR", "DGS7": "BC_7YEAR", "DGS10": "BC_10YEAR",
    "DGS20": "BC_20YEAR", "DGS30": "BC_30YEAR",
}

#: The only User-Agent shape this feed serves. See the module docstring.
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
}


class UnknownSeries(KeyError):
    pass


def yields(series, *, year: int | None = None, cache_ttl: float | None = 3600,
           user_agent: str | None = BROWSER_UA):
    """Observations for ``series`` over ``year`` (default: this year).

    Missing days are absent rather than zero-filled: Treasury publishes no row
    for a non-business day, and inventing one would be a silent guess.
    """
    unknown = [s for s in series if s not in FIELDS]
    if unknown:
        raise UnknownSeries(f"no Treasury field for {unknown}; known: {sorted(FIELDS)}")

    year = year or date.today().year
    url = FEED.format(year=year)
    resp = http.get(url, user_agent=user_agent, cache_ttl=cache_ttl)

    root = ET.fromstring(resp.body)
    out: list[Observation] = []
    for entry in root.findall(".//a:entry", _NS):
        props = entry.find(".//m:properties", _NS)
        if props is None:
            continue
        vals = {c.tag.split("}")[1]: c.text for c in props}
        raw_date = vals.get("NEW_DATE")
        if not raw_date:
            continue
        obs_date = datetime.fromisoformat(raw_date).date()
        for canonical in series:
            text = vals.get(FIELDS[canonical])
            if text in (None, "", "."):
                continue          # Axiom 7: absent is not invalid
            try:
                value = Decimal(text)
            except InvalidOperation:
                continue
            out.append(Observation(canonical, obs_date, value, NAMESPACE))

    out.sort(key=lambda o: (o.series, o.obs_date))

    r = current()
    if r is not None:
        r.input(NAMESPACE, f"daily_treasury_yield_curve/{year}",
                fields=sorted(FIELDS[s] for s in series), rows=len(out))
    return out
