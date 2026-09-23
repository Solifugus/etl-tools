# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""``Money`` -- an exact integer of scaled units, with its currency attached.

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

**Four guard digits below the minor unit**, measured against gBASIC 0.2.2
rather than assumed: USD stores 6 decimal places, JPY 4, KWD 7. Sub-cent
amounts are ordinary in finance -- fuel is posted at $3.459 a gallon,
electricity quoted at $0.10432 a kWh -- and rounding them away at construction
is a silent loss of exactly the kind axiom 8 forbids. So **display** rounds to
the minor unit and the **value** does not: ``Money.of("3.459", "USD")`` shows
``3.46`` and ``* 10`` is ``34.59``, not ``34.60``.

The split on excess precision follows gBASIC's: precision you **wrote** past
the guard digits is refused, because you wrote something money cannot hold;
precision a **calculation** produced is rounded, because ``price * Decimal("1.08")``
always carries more digits than that and refusing it would make the type
unusable.

One **sanctioned deviation** (``porting-plan.md`` §1.2): gBASIC's money is an
int64 and raises past about ±$9.22 trillion. Python's ints do not have that
ceiling and none is imposed here, so a value gBASIC refuses is accepted. The
divergence runs in the direction of capability, and a parity case would have
to encode gBASIC's limit as though it were a rule rather than an artefact.
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

#: Digits kept *below* the minor unit. Measured from gBASIC 0.2.2.
GUARD_DIGITS = 4


class CurrencyMismatch(TypeError):
    """Two different currencies met in one operation."""


def exponent(currency: str) -> int:
    """Minor units per major unit, as a power of ten. USD 2, JPY 0, KWD 3."""
    return _EXPONENTS.get(currency.upper(), 2)


def stored_places(currency: str) -> int:
    """Decimal places actually held: the minor unit plus the guard digits."""
    return exponent(currency) + GUARD_DIGITS


class Money:
    """An exact amount in one currency, held as an integer of minor units."""

    __slots__ = ("_units", "_currency")

    def __init__(self, units: int, currency: str):
        """Low-level: *units* is at :func:`stored_places` scale. Prefer :meth:`of`."""
        if not isinstance(units, int) or isinstance(units, bool):
            raise TypeError(
                f"Money() takes an int of scaled units, not {type(units).__name__}. "
                "Use Money.of() for a decimal amount."
            )
        object.__setattr__(self, "_units", units)
        object.__setattr__(self, "_currency", currency.upper())

    # --- construction ----------------------------------------------------

    @classmethod
    def of(cls, currency: str, amount: str | int | Decimal,
           *, rounding: str = DEFAULT_ROUNDING) -> "Money":
        """From a major-unit amount. ``Money.of("USD", "12.34")``.

        Currency first, matching gBASIC's ``money.of(code, text)``. It reads
        the way an amount is written -- the symbol precedes the digits.

        ``float`` is refused: by the time a float arrives the value it was
        written as may already be gone, and this type exists to not do that.
        Pass a string, an int, or a Decimal.
        """
        if isinstance(amount, float):
            raise TypeError(
                "Money.of() refuses float -- 92233720368547.75 is already "
                f"{92233720368547.75!r} before this call sees it. "
                'Pass a string: Money.of("USD", "92233720368547.75").'
            )
        if isinstance(amount, bool):
            raise TypeError("Money.of() refuses bool.")
        try:
            dec = Decimal(amount)
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValueError(f"not a decimal amount: {amount!r}") from e
        if not dec.is_finite():
            raise ValueError(f"amount is not finite: {amount!r}")
        cur = currency.upper()
        places = stored_places(cur)
        written = -dec.as_tuple().exponent
        if written > places:
            # What you WROTE is refused; what a calculation produces is rounded.
            raise ValueError(
                f"{cur}: money text has more decimal places than the currency "
                f"can store ({cur} stores {places})")
        return cls(int((dec.scaleb(places)).to_integral_value(rounding=rounding)), cur)

    @classmethod
    def from_minor(cls, currency: str, minor: int) -> "Money":
        """From whole minor units -- cents, yen, fils. No guard digits set."""
        if not isinstance(minor, int) or isinstance(minor, bool):
            raise TypeError("from_minor() takes an int")
        return cls(minor * 10 ** GUARD_DIGITS, currency)

    @classmethod
    def zero(cls, currency: str) -> "Money":
        return cls(0, currency)

    # --- reading ---------------------------------------------------------

    @property
    def units(self) -> int:
        """The exact scaled integer, guard digits included. The value itself."""
        return self._units

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def amount(self) -> Decimal:
        """Major units, exactly, guard digits included. Never a float."""
        return Decimal(self._units).scaleb(-stored_places(self._currency))

    @property
    def minor(self) -> int:
        """Rounded to whole minor units -- what posts to a ledger."""
        return int(self.amount.scaleb(exponent(self._currency))
                   .to_integral_value(rounding=DEFAULT_ROUNDING))

    @property
    def posted(self) -> Decimal:
        """The displayed amount: rounded to the minor unit, exactly."""
        return Decimal(self.minor).scaleb(-exponent(self._currency))

    def text(self, places: int | None = None) -> str:
        """The exit that keeps the guard digits -- gBASIC's ``money.text``.

        With no width it renders at the **storage scale**, so the text reads
        back through :meth:`of` as the same value, which is what storing money
        as decimal text in a database or a JSON document needs. ``str()``
        renders at the minor unit instead, which is right on a screen and
        lossy in a file.
        """
        if places is None:
            places = stored_places(self._currency)
        elif not isinstance(places, int) or isinstance(places, bool) or not 0 <= places <= 18:
            raise ValueError("places must be a whole number from 0 to 18")
        q = Decimal(1).scaleb(-places)
        return str(self.amount.quantize(q, rounding=DEFAULT_ROUNDING))

    def rounded(self) -> "Money":
        """This amount with the guard digits discarded. An explicit loss."""
        return Money.from_minor(self._currency, self.minor)

    @property
    def is_exact_at_minor_unit(self) -> bool:
        """True when nothing is hiding below the minor unit."""
        return self._units % (10 ** GUARD_DIGITS) == 0

    def __repr__(self) -> str:
        return f'Money.of("{self._currency}", "{self.text()}")'

    def __str__(self) -> str:
        """Display rounds to the minor unit; the value does not."""
        return f"{self.posted} {self._currency}"

    def __format__(self, spec: str) -> str:
        return format(self.posted, spec) if spec else str(self)

    # --- identity --------------------------------------------------------

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._units == other._units and self._currency == other._currency

    def __hash__(self) -> int:
        return hash((Money, self._units, self._currency))

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
        return Money(self._units + other._units, self._currency)

    def __sub__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._same(other)
        return Money(self._units - other._units, self._currency)

    def __neg__(self) -> "Money":
        return Money(-self._units, self._currency)

    def __abs__(self) -> "Money":
        return Money(abs(self._units), self._currency)

    def __mul__(self, factor: int | Decimal) -> "Money":
        """Exact for an int. For a Decimal, rounds once, at the end."""
        if isinstance(factor, bool) or isinstance(factor, float):
            raise TypeError(
                "Money * float is refused -- it would leave exact arithmetic. "
                "Pass an int or a Decimal."
            )
        if isinstance(factor, int):
            return Money(self._units * factor, self._currency)
        if isinstance(factor, Decimal):
            product = Decimal(self._units) * factor
            return Money(int(product.to_integral_value(rounding=DEFAULT_ROUNDING)),
                         self._currency)
        return NotImplemented

    __rmul__ = __mul__

    def __lt__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._same(other)
        return self._units < other._units

    def __le__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._same(other)
        return self._units <= other._units

    def __gt__(self, other: "Money") -> bool:
        return not self <= other

    def __ge__(self, other: "Money") -> bool:
        return not self < other

    # --- division, which is where money is actually lost -----------------

    def __truediv__(self, divisor: int | Decimal) -> "Money":
        """Divide, keeping the guard digits. ``(m / 3) * 3`` comes back to ``m``.

        For splitting an amount among payees use :meth:`allocate` instead --
        this keeps the fractional remainder, which is right for a rate and
        wrong for a payment.
        """
        if isinstance(divisor, bool) or isinstance(divisor, float):
            raise TypeError(
                "Money / float is refused -- it would leave exact arithmetic. "
                "Pass an int or a Decimal.")
        if not isinstance(divisor, (int, Decimal)):
            return NotImplemented
        if divisor == 0:
            raise ZeroDivisionError("Money / 0")
        quotient = Decimal(self._units) / Decimal(divisor)
        return Money(int(quotient.to_integral_value(rounding=DEFAULT_ROUNDING)),
                     self._currency)

    # --- splitting, which is where money is actually lost ----------------

    def allocate(self, weights) -> tuple["Money", ...]:
        """Split across *weights* losing **nothing**, at the minor unit.

        The reason this exists instead of :meth:`__truediv__`: 100 divided
        three ways is 33.33 three times and a cent unaccounted for. Rounding
        each share independently loses it silently. This distributes the
        remainder one minor unit at a time, largest weight first, so the parts
        always sum back to the whole -- which is the only property a ledger
        cares about.

        Allocation works at the **minor unit**, not the guard digits, because
        a payee is paid in cents. An amount carrying guard digits is therefore
        rounded first, and :attr:`is_exact_at_minor_unit` says in advance
        whether that will lose anything.
        """
        weights = [Decimal(w) for w in weights]
        if not weights:
            raise ValueError("allocate() needs at least one weight")
        if any(w < 0 for w in weights):
            raise ValueError("allocate() weights must not be negative")
        total = sum(weights)
        if total == 0:
            raise ValueError("allocate() weights must not sum to zero")

        whole = self.minor
        shares = [int((Decimal(whole) * w / total)
                      .to_integral_value(rounding="ROUND_DOWN")) for w in weights]
        remainder = whole - sum(shares)
        order = sorted(range(len(weights)), key=lambda i: weights[i], reverse=True)
        step = 1 if remainder >= 0 else -1
        for k in range(abs(remainder)):
            shares[order[k % len(order)]] += step
        return tuple(Money.from_minor(self._currency, s) for s in shares)

    def split(self, n: int) -> tuple["Money", ...]:
        """Into *n* equal parts, losing nothing. ``allocate`` with equal weights."""
        if n < 1:
            raise ValueError("split() needs a positive number of parts")
        return self.allocate([1] * n)
