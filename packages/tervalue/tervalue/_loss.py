# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""``LossReport`` -- axiom 8: loss must be explicit.

A transform that narrows, truncates, rounds or drops must be able to say so,
and the caller must be able to ask without knowing in advance what kind of
loss to expect. A conversion that quietly succeeds is indistinguishable from
one that had nothing to lose, and the two need different decisions.

The report is a value, not a log line: it is returned alongside the result,
survives being passed on, and merges with other reports so a pipeline can hand
back one account of everything it lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Loss:
    """One thing given up, and where."""

    kind: str           #: "truncated", "rounded", "narrowed", "dropped", "unmapped"
    detail: str         #: what it was, in terms a person can check
    where: str | None = None   #: field, column or record -- the caller's own naming

    def __str__(self) -> str:
        at = f" at {self.where}" if self.where else ""
        return f"{self.kind}{at}: {self.detail}"


@dataclass(frozen=True, slots=True)
class LossReport:
    """Everything one transform gave up. Empty is the common, honest case."""

    losses: tuple[Loss, ...] = field(default_factory=tuple)

    @classmethod
    def none(cls) -> "LossReport":
        return cls(())

    def plus(self, kind: str, detail: str, where: str | None = None) -> "LossReport":
        return LossReport(self.losses + (Loss(kind, detail, where),))

    def merge(self, other: "LossReport") -> "LossReport":
        return LossReport(self.losses + other.losses)

    @property
    def lossless(self) -> bool:
        return not self.losses

    def of_kind(self, kind: str) -> tuple[Loss, ...]:
        return tuple(l for l in self.losses if l.kind == kind)

    def __len__(self) -> int:
        return len(self.losses)

    def __iter__(self):
        return iter(self.losses)

    def __bool__(self):
        raise TypeError(
            "a LossReport has no truth value -- 'bool(report)' reads as "
            "'was there loss?' to one person and 'did it succeed?' to the "
            "next. Use .lossless or len()."
        )

    def __str__(self) -> str:
        if self.lossless:
            return "no loss"
        return "; ".join(str(l) for l in self.losses)
