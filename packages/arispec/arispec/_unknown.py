# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""``UNKNOWN`` -- a cell the recognizers could not read.

A value matching no rule becomes UNKNOWN **for that cell alone**: never a
silent zero, and never a raise that sinks a 100,000-line import because one
teller's bait cash was keyed as ``$8,0000``.

arispec carries its own sentinel rather than importing the family's
(``packaging.md`` §3): ARI sits at the *edge*, and a library for parsing
legacy reports should not make anyone take a dependency to find out that a
cell was unreadable. Values are lifted into ``tervalue`` once, at a single
documented boundary, rather than crossing back and forth.
"""

from __future__ import annotations

__all__ = ["UNKNOWN"]


class _Unknown:
    """The single unknown value. Compare with ``is``."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "UNKNOWN"

    def __bool__(self):
        raise TypeError(
            "UNKNOWN has no truth value -- an unreadable cell is not an empty "
            "one. Test it with 'x is UNKNOWN'.")

    def __reduce__(self):
        return (_Unknown, ())

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


UNKNOWN = _Unknown()
