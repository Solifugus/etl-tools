# arispec

Anchor-relative identification: declarative extraction from irregular text and grids

**Status: name reserved. Nothing is implemented yet.**

Declarative extraction of fields from irregular, semi-structured text: legacy
print reports, mainframe spool, teller totals, and the 2D grids that arrive as
spreadsheets.

ARI locates a value by anchoring on nearby landmarks and **delimiting it by
type** -- "the last money-shaped token on this row" -- rather than by a fixed
column or a column heading. Neither of those survives contact with real
reports: headings drift out of alignment with their own data over decades of
separate edits, and a trailing-minus negative is one column wider than the
positive above it because the sign is appended after right-justification.

The design and schedule live in [the roadmap](https://github.com/Solifugus/etl-tools/blob/master/docs/roadmap.md).

Apache-2.0. Copyright 2026 Matthew C. Tedder.
