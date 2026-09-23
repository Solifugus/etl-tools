# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""``Outcome`` -- three-valued, because two values lose the case that matters.

A reader that returns a value or raises has only two answers, and the field it
could not interpret has to become one of them: a ``None`` that downstream code
will treat as absent, or an exception that stops a 100,000-record file because
one trace number had a letter in it.

Neither is right, and the third answer is the useful one:

===========  ==========================================================
``ok``       interpreted; ``value`` holds it
``unknown``  a value was there and could not be determined -- axiom 7
``invalid``  a value was there and is wrong; ``reason`` says how
===========  ==========================================================

``raw`` is kept on all three (axiom 1, preserve the source), so an ``invalid``
can be shown to a person, and an ``unknown`` can be re-read by a later adapter
revision without going back to the file.

``source`` is deliberately untyped. What a source reference *is* belongs to
whoever computed it -- in ``finio`` it is reconstructed on demand from a
retained source, which makes it an artefact of that library's model rather
than a neutral value. See ``packaging.md`` §9.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ._unknown import UNKNOWN

OK = "ok"
UNKNOWN_STATUS = "unknown"
INVALID = "invalid"
STATUSES = (OK, UNKNOWN_STATUS, INVALID)


@dataclass(frozen=True, slots=True)
class Outcome:
    """One interpreted value, and what is true about the interpretation."""

    status: str
    value: Any = UNKNOWN
    raw: Any = None
    reason: str | None = None
    source: Any = field(default=None, compare=False)

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(
                f"status must be one of {STATUSES}, not {self.status!r}")
        if self.status == INVALID and not self.reason:
            raise ValueError(
                "an invalid Outcome must carry a reason -- "
                "'this is wrong' without 'how' cannot be acted on")

    # --- construction ----------------------------------------------------

    @classmethod
    def ok(cls, value: Any, raw: Any = None, *, source: Any = None) -> "Outcome":
        return cls(OK, value, raw, None, source)

    @classmethod
    def unknown(cls, raw: Any = None, *, reason: str | None = None,
                source: Any = None) -> "Outcome":
        return cls(UNKNOWN_STATUS, UNKNOWN, raw, reason, source)

    @classmethod
    def invalid(cls, reason: str, raw: Any = None, *, source: Any = None) -> "Outcome":
        return cls(INVALID, UNKNOWN, raw, reason, source)

    # --- reading ---------------------------------------------------------

    @property
    def is_ok(self) -> bool:
        return self.status == OK

    @property
    def is_unknown(self) -> bool:
        return self.status == UNKNOWN_STATUS

    @property
    def is_invalid(self) -> bool:
        return self.status == INVALID

    def __bool__(self):
        raise TypeError(
            "an Outcome has no truth value -- 'unknown' and 'invalid' are "
            "different answers and bool() would merge them. "
            "Use .is_ok, .is_unknown or .is_invalid."
        )

    def unwrap(self) -> Any:
        """The value, or raise. For code that genuinely cannot continue."""
        if self.is_ok:
            return self.value
        detail = f": {self.reason}" if self.reason else ""
        raise ValueError(f"Outcome is {self.status}{detail} (raw={self.raw!r})")

    def or_else(self, default: Any) -> Any:
        """The value if ok, else *default*. The explicit, visible fallback."""
        return self.value if self.is_ok else default

    def map(self, fn) -> "Outcome":
        """Apply *fn* to an ok value; pass unknown and invalid through."""
        if not self.is_ok:
            return self
        return Outcome(OK, fn(self.value), self.raw, None, self.source)
