# tervalue

Values that can say what they do not know: `UNKNOWN`, `Outcome`, `LossReport`, `Money`.

Four types, no dependencies, and nothing else. This is the kernel a family of
data libraries shares so that a value crossing between them is the same value
on both sides.

```python
from tervalue import Money, Outcome, UNKNOWN

Money.of("100.00", "USD").allocate([1, 1, 1])
# (Money.of("33.34", "USD"), Money.of("33.33", "USD"), Money.of("33.33", "USD"))
# -- the parts sum back to the whole, which is the only property a ledger cares about

Money.of(12.34, "USD")        # TypeError: refuses float
Money.of("1", "USD") + Money.of("1", "EUR")   # CurrencyMismatch
```

### The distinctions it exists to keep

**`UNKNOWN` is not `None`.** `None` means "nothing was supplied". `UNKNOWN`
means "a value was there and could not be determined". Arithmetic propagates
it, because that is the true answer; `bool()` refuses it, because a truth value
is a decision and there is not one to make.

**`Outcome` has three statuses, not two.** `ok`, `unknown`, `invalid` — and an
`invalid` must carry a reason, because "this is wrong" without "how" cannot be
acted on. The raw text is kept on all three, so an unknown can be re-read later
by a better parser without going back to the file.

**`LossReport` is returned, not logged.** A conversion that quietly succeeds is
indistinguishable from one that had nothing to lose, and those need different
decisions.

**`Money` is an exact integer of minor units.** Scale comes from the currency
(JPY 0, USD 2, KWD 3), `float` is refused at construction, arithmetic never
leaves `int`/`Decimal`, rounding is half-even on the *text*, and two currencies
never mix — a conversion needs a rate, which is a fact about a date, not a
property of a value.

Ported from gBASIC's `money` type, closing the four defects its own design
document records against its first implementation. Each has a test that names it.

Apache-2.0. Copyright 2026 Matthew C. Tedder.
