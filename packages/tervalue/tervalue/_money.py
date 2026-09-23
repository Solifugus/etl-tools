# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""``Money`` -- an exact integer of minor units, with its currency attached.

Ported from gBASIC's ``money`` type (``docs/money_design.md``), including the
four defects that document records against its own first implementation. Each
is closed here by construction rather than by care:

1. **There was no exact way to construct one.** The constructor took a number,
   which was already a ``float`` by the time it arrived, so the type's own
   int64 range was unreachable through its own constructor. Here ``float`` is
   **refused** -- see :meth:`Money.of`.
2. **``*`` and ``/`` left integer arithmetic.** Both routed through a divide
   and a multiply by 100 in floating point, corrupting a value the caller had
   already got right. Here every operation stays in ``int``/``Decimal``.
3. **Scale was hardcoded to cents.** JPY (exponent 0) and KWD/BHD/TND
   (exponent 3) had no correct representation. Here scale comes from the
   currency.
4. **The rounding rule at ``.5`` was not well-defined** -- it looked like
   banker's rounding and was actually half-away-from-zero over binary floats,
   so the rule depended on the literal's representation rather than its text.
   Here it is ``ROUND_HALF_EVEN``, stated, and overridable per call.

Two currencies never mix: an operation between USD and EUR raises rather than
inventing a rate. A rate is a *fact about a date*, not a property of a value.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any

#: Minor-unit exponents that are not 2. ISO 4217's own exceptions.
_EXPONENTS = {
    "BIF": 0, "CLP": 0, "DJF": 0, "GNF": 0, "ISK": 0, "JPY": 0, "KMF": 0,
    "KRW": 0, "PYG": 0, "RWF": 0, "UGX": 0, "UYI": 0, "VND": 0, "VUV": 0,
    "XAF": 0, "XOF": 0, "XPF": 0,
    "BHD": 3, "IQD": 3, "JOD": 3, "KWD": 3, "LYD": 3, "OMR": 3, "TND": 3,
    "CLF": 4,
}

DEFAULT_ROUNDING = ROUND_HALF_EVEN


class CurrencyMismatch(TypeError):
    """Two different currencies met in one operation."""


def exponent(currency: str) -> int:
    """Minor units per major unit, as a power of ten. USD 2, JPY 0, KWD 3."""
    return _EXPONENTS.get(currency.upper(), 2)


class Money:
    """An exact amount in one currency, held as an integer of minor units."""

    __slots__ = ("_minor", "_currency")

    def __init__(self, minor: int, currency: str):
        """Low-level: *minor* is already in minor units. Prefer :meth:`of`."""
        if not isinstance(minor, int) or isinstance(minor, bool):
            raise TypeError(
                f"Money() takes an int of minor units, not {type(minor).__name__}. "
                "Use Money.of() for a decimal amount."
            )
        object.__setattr__(self, "_minor", minor)
        object.__setattr__(self, "_currency", currency.upper())

    # --- construction ----------------------------------------------------

    @classmethod
    def of(cls, amount: str | int | Decimal, currency: str,
           *, rounding: str = DEFAULT_ROUNDING) -> "Money":
        """From a major-unit amount. ``Money.of("12.34", "USD")``.

        ``float`` is refused: by the time a float arrives the value it was
        written as may already be gone, and this type exists to not do that.
        Pass a string, an int, or a Decimal.
        """
        if isinstance(amount, float):
            raise TypeError(
                "Money.of() refuses float -- 92233720368547.75 is already "
                f"{92233720368547.75!r} before this call sees it. "
                'Pass a string: Money.of("92233720368547.75", "USD").'
            )
        if isinstance(amount, bool):
            raise TypeError("Money.of() refuses bool.")
        try:
            dec = Decimal(amount)
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValueError(f"not a decimal amount: {amount!r}") from e
        if not dec.is_finite():
            raise ValueError(f"amount is not finite: {amount!r}")
        scale = 10 ** exponent(currency)
        return cls(int((dec * scale).to_integral_value(rounding=rounding)), currency)

    @classmethod
    def zero(cls, currency: str) -> "Money":
        return cls(0, currency)

    # --- reading ---------------------------------------------------------

    @property
    def minor(self) -> int:
        """The exact integer of minor units. The value; everything else is a view."""
        return self._minor

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def amount(self) -> Decimal:
        """Major units, exactly. Never a float."""
        return Decimal(self._minor).scaleb(-exponent(self._currency))

    def __repr__(self) -> str:
        return f'Money.of("{self.amount}", "{self._currency}")'

    def __str__(self) -> str:
        return f"{self.amount} {self._currency}"

    def __format__(self, spec: str) -> str:
        return format(self.amount, spec) if spec else str(self)

    # --- identity --------------------------------------------------------

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._minor == other._minor and self._currency == other._currency

    def __hash__(self) -> int:
        return hash((Money, self._minor, self._currency))

    def __setattr__(self, *_):
        raise AttributeError("Money is immutable")

    # --- arithmetic ------------------------------------------------------

    def _same(self, other: "Money") -> None:
        if self._currency != other._currency:
            raise CurrencyMismatch(
                f"{self._currency} and {other._currency} do not mix. "
                "A conversion needs a rate, which is a fact about a date, "
                "not a property of either value."
            )

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._same(other)
        return Money(self._minor + other._minor, self._currency)

    def __sub__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._same(other)
        return Money(self._minor - other._minor, self._currency)

    def __neg__(self) -> "Money":
        return Money(-self._minor, self._currency)

    def __abs__(self) -> "Money":
        return Money(abs(self._minor), self._currency)

    def __mul__(self, factor: int | Decimal) -> "Money":
        """Exact for an int. For a Decimal, rounds once, at the end."""
        if isinstance(factor, bool) or isinstance(factor, float):
            raise TypeError(
                "Money * float is refused -- it would leave exact arithmetic. "
                "Pass an int or a Decimal."
            )
        if isinstance(factor, int):
            return Money(self._minor * factor, self._currency)
        if isinstance(factor, Decimal):
            product = Decimal(self._minor) * factor
            return Money(int(product.to_integral_value(rounding=DEFAULT_ROUNDING)),
                         self._currency)
        return NotImplemented

    __rmul__ = __mul__

    def __lt__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._same(other)
        return self._minor < other._minor

    def __le__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._same(other)
        return self._minor <= other._minor

    def __gt__(self, other: "Money") -> bool:
        return not self <= other

    def __ge__(self, other: "Money") -> bool:
        return not self < other

    # --- division, which is where money is actually lost -----------------

    def allocate(self, weights) -> tuple["Money", ...]:
        """Split across *weights* losing **nothing**.

        The reason this exists instead of ``__truediv__``: 100 divided three
        ways is 33.33 three times and a cent unaccounted for. Rounding each
        share independently loses it silently. This distributes the remainder
        one minor unit at a time, largest weight first, so the parts always
        sum back to the whole -- which is the only property a ledger cares
        about.
        """
        weights = [Decimal(w) for w in weights]
        if not weights:
            raise ValueError("allocate() needs at least one weight")
        if any(w < 0 for w in weights):
            raise ValueError("allocate() weights must not be negative")
        total = sum(weights)
        if total == 0:
            raise ValueError("allocate() weights must not sum to zero")

        shares = [int((Decimal(self._minor) * w / total)
                      .to_integral_value(rounding="ROUND_DOWN")) for w in weights]
        remainder = self._minor - sum(shares)
        order = sorted(range(len(weights)), key=lambda i: weights[i], reverse=True)
        step = 1 if remainder >= 0 else -1
        for k in range(abs(remainder)):
            shares[order[k % len(order)]] += step
        return tuple(Money(s, self._currency) for s in shares)

    def split(self, n: int) -> tuple["Money", ...]:
        """Into *n* equal parts, losing nothing. ``allocate`` with equal weights."""
        if n < 1:
            raise ValueError("split() needs a positive number of parts")
        return self.allocate([1] * n)
