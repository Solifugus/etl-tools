# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Pattern tokens: a ``"literal"`` or a ``/regex/``, and how to find one.

A spec names text in exactly two ways, and the quoting says which. Keeping
that decision in one place is what lets every locator, every section
``starts(...)`` and every type rule accept both without each deciding again.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Hit", "find_token", "indent_of", "is_blank", "is_regex_token",
           "line_matches", "unquote"]


@dataclass(frozen=True, slots=True)
class Hit:
    """Where a token matched, and what it captured."""

    text: str
    start: int
    length: int
    groups: tuple = ()

    @property
    def end(self) -> int:
        return self.start + self.length


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def is_blank(line: str) -> bool:
    return not line.strip()


def unquote(s: str) -> str:
    """Strip a matching pair of surrounding quotes or slashes, if present."""
    t = s.strip()
    if len(t) < 2:
        return t
    if (t[0] == '"' and t[-1] == '"') or (t[0] == "/" and t[-1] == "/"):
        return t[1:-1]
    return t


def is_regex_token(s: str) -> bool:
    """Is this token a ``/regex/`` rather than a ``"literal"``?"""
    t = s.strip()
    return len(t) >= 2 and t[0] == "/" and t[-1] == "/"


def find_token(hay: str, token: str) -> Hit | None:
    """Find *token* in *hay*: ``/re/`` as a regex, anything else literally."""
    body = unquote(token)
    if is_regex_token(token):
        m = re.search(body, hay)
        if m is None:
            return None
        return Hit(m.group(0), m.start(), m.end() - m.start(), m.groups())
    idx = hay.find(body)
    if idx < 0:
        return None
    return Hit(body, idx, len(body), ())


def line_matches(line: str, token: str) -> bool:
    return bool(token) and find_token(line, token) is not None
