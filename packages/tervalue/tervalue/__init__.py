# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""tervalue -- values that can say what they do not know.

The kernel four libraries share: ``UNKNOWN``, ``Outcome``, ``LossReport`` and
``Money``. Nothing else is admitted (``packaging.md`` §9.4), it depends on
nothing but the standard library, and once it reaches 1.0 it only ever gains
members -- because everything above it depends on it, and a kernel that keeps
moving forces its cadence on every library that does not want it.

    >>> from tervalue import Money, Outcome, UNKNOWN
    >>> Money.of("100.00", "USD").allocate([1, 1, 1])
    (Money.of("33.34", "USD"), Money.of("33.33", "USD"), Money.of("33.33", "USD"))
    >>> Outcome.invalid("not a date", raw="32/13/2026").is_ok
    False

What is deliberately *not* here: a source reference. Provenance is computed
differently by each library that computes it, and pinning one shape here would
make this the value layer of whichever library got there first.
"""

from ._loss import Loss, LossReport
from ._money import (DEFAULT_ROUNDING, GUARD_DIGITS, CurrencyMismatch, Money,
                     exponent, stored_places)
from ._outcome import INVALID, OK, STATUSES, UNKNOWN_STATUS, Outcome
from ._unknown import UNKNOWN

__all__ = [
    "UNKNOWN",
    "Outcome", "OK", "UNKNOWN_STATUS", "INVALID", "STATUSES",
    "Loss", "LossReport",
    "Money", "CurrencyMismatch", "exponent", "stored_places",
    "GUARD_DIGITS", "DEFAULT_ROUNDING",
]
__version__ = "0.1.0"
