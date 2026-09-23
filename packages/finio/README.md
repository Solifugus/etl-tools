# finio

A financial adapter framework: payment and statement formats, with provenance

**Status: name reserved. Nothing is implemented yet.**

Formats as data rather than as functions: NACHA, BAI2, OFX, CAMT, PAIN.001 and
the rest, over one framework that retains the source, records where every
interpreted value came from, reports what a lossy transform lost, and refuses
to guess which format a file is when the evidence is ambiguous.

The distinction it is built on: **unknown is not invalid**, and a parser that
silently drops the remainder it could not read cannot afterwards answer where
a value came from.

The design and schedule live in [the roadmap](https://github.com/Solifugus/etl-tools/blob/master/docs/roadmap.md).

Apache-2.0. Copyright 2026 Matthew C. Tedder.
