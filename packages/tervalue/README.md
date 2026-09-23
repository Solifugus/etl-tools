# tervalue

Values that can say what they do not know: `UNKNOWN`, `Outcome`, `LossReport`, `Money`.

Four types, no dependencies, and nothing else. This is the kernel a family of
data libraries shares so that a value crossing between them is the same value
on both sides.

```python
from tervalue import Money, Outcome, UNKNOWN

Money.of("USD", "100.00").allocate([1, 1, 1])
# (Money.of("USD", "33.34"), Money.of("USD", "33.33"), Money.of("USD", "33.33"))
# -- the parts sum back to the whole, which is the only property a ledger cares about

Money.of("USD", 12.34)        # TypeError: refuses float
Money.of("USD", "1") + Money.of("EUR", "1")   # CurrencyMismatch
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

**`Money` keeps four guard digits below the minor unit.** USD stores six
decimal places, JPY four, KWD seven. Sub-cent amounts are ordinary in finance —
fuel is posted at $3.459 a gallon — so **display** rounds to the minor unit and
the **value** does not:

```python
fuel = Money.of("USD", "3.459")
str(fuel)        # '3.46 USD'   <- display rounds
str(fuel * 10)   # '34.59 USD'  <- the value did not
fuel.text()      # '3.459000'   <- the exit that keeps everything, round-trips
```

`float` is refused at construction, arithmetic never leaves `int`/`Decimal`,
rounding is half-even on the *text*, precision you wrote past the guard digits
is refused while precision a calculation produced is rounded, and two
currencies never mix — a conversion needs a rate, which is a fact about a date,
not a property of a value.

Ported from gBASIC's `money` type, closing the four defects its own design
document records against its first implementation. Each has a test that names
it, and `parity/` runs the same cases against both trees.

Apache-2.0. Copyright 2026 Matthew C. Tedder.
