# ARI fixtures

**Every file here is SYNTHETIC.** Nothing was captured from anywhere. These
are hand-authored or generated page images that reproduce the *layout* of a
class of report. They contain **no real account, member, employee or
institution data**; names, numbers, dates and identifiers are invented.

The distinction matters both ways: a reader who finds a file here that
resembles a production report must be able to tell at once that it is
invented, and the fixtures must never become a route by which real data
enters the repository.

Copied from the gBASIC tree (`examples/fixtures/ari/`), same author, same
licence, so arispec's suite stands alone.

| file | shape modelled | why it exists |
|---|---|---|
| `teller_totals.rpt` | credit-union teller totals | The **irregularity** fixture, hand-made because a template cannot invent the inconsistencies a real report has. No form feeds — pagination is the header line alone. Summary fields print in a different order for different tellers; the `Amount` heading is four columns adrift of its data; the negative row is one column wider than the positives; `Teller #:` and `Teller#:` are the same field spelled two ways; one bait-cash cell is malformed. |
| `teller_totals_generated.rpt` | the same, at scale | The **variation** fixture: 230 lines, 4 pages, form feeds, and money printed in a *different dialect per branch* — which is what the union recognizer exists for. |
| `delinquency.rpt` | consolidated delinquency register | The **vertical locator** fixture. A label alone on its line with the value below it; an amount printed two lines *above* its label; a dotted leader to the right margin; a label-to-value gap that varies 1, 2, 2, 3 lines down the report; records that wrap onto a `COLLATERAL:` continuation line; and dates in `DD/MM/YYYY` of which the ambiguous minority must be refused rather than guessed. |
