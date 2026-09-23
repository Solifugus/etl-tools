# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""finio -- a financial adapter framework.

Formats as data rather than as functions: NACHA, BAI2, OFX, CAMT, PAIN.001 and
the rest, over one framework that retains the source, records where every
interpreted value came from, reports what a lossy transform lost, and refuses
to guess which format a file is when the evidence is ambiguous.

The distinction it is built on: **unknown is not invalid**, and a parser that
silently drops the remainder it could not read cannot afterwards answer where
a value came from.

**This release reserves the name.** Nothing is implemented yet. The design and
schedule are at https://github.com/Solifugus/etl-tools/blob/master/docs/roadmap.md -- see Wave 3.
"""

__version__ = "0.0.1"
