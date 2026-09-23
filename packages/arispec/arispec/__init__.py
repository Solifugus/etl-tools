# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""ARI -- anchor-relative identification.

Declarative extraction of fields from irregular, semi-structured text: legacy
print reports, mainframe spool, teller totals, and the 2D grids that arrive as
spreadsheets.

ARI locates a value by anchoring on nearby landmarks and **delimiting it by
type** -- "the last money-shaped token on this row" -- rather than by a fixed
column or a column heading. Neither of those survives contact with real
reports: headings drift out of alignment with their own data over decades of
separate edits, and a trailing-minus negative is one column wider than the
positive above it because the sign is appended after right-justification.

**This release reserves the name.** Nothing is implemented yet. The design and
schedule are at https://github.com/Solifugus/etl-tools/blob/master/docs/roadmap.md -- see Wave 1.
"""

__version__ = "0.0.1"
