"""The one row shape every source yields."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Observation:
    series: str          # canonical id, e.g. "DGS5"
    obs_date: date       # the day observed, not the day fetched
    value: Decimal       # percent, e.g. Decimal("4.78")
    source: str          # namespace of the origin, for lineage
