# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""``UNKNOWN`` -- a value exists and is not known.

``None`` already means "nothing was supplied". Axiom 7 needs a *different*
thing: the cell was there, it had something in it, and what it held could not
be determined. Conflating the two loses the distinction in the first module
that reads a file with a blank field in it.

Two deliberate asymmetries, both of which come straight from the axioms:

* **Arithmetic propagates.** ``UNKNOWN + 1`` is ``UNKNOWN``. That is not a
  guess, it is the correct answer, and refusing it would push every caller
  into writing the propagation by hand.
* **``bool()`` refuses.** A truth value is a decision, and there is not one to
  make. ``if x:`` on an unknown would silently take the false branch, which is
  precisely the silent guess axiom 6 forbids. Test with ``x is UNKNOWN``.
"""

from __future__ import annotations


class _Unknown:
    """The type of :data:`UNKNOWN`. Not instantiable a second time."""

    __slots__ = ()
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNKNOWN"

    def __reduce__(self):
        return (_Unknown, ())

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __bool__(self):
        raise TypeError(
            "UNKNOWN has no truth value -- an unknown is not false. "
            "Test it with 'x is UNKNOWN'."
        )

    def __hash__(self) -> int:
        return hash(_Unknown)

    # Arithmetic and comparison propagate rather than raise: the result of
    # combining something with an unknown genuinely is unknown.
    def _propagate(self, *_args):
        return self

    __add__ = __radd__ = __sub__ = __rsub__ = _propagate
    __mul__ = __rmul__ = __truediv__ = __rtruediv__ = _propagate
    __floordiv__ = __rfloordiv__ = __mod__ = __rmod__ = _propagate
    __pow__ = __rpow__ = __neg__ = __pos__ = __abs__ = _propagate
    __round__ = _propagate

    # Ordering is unknown too; equality is identity, because UNKNOWN is one
    # marker rather than a population of indistinguishable values.
    __lt__ = __le__ = __gt__ = __ge__ = _propagate


#: The single unknown marker. Compare with ``is``, never with ``==``.
UNKNOWN = _Unknown()
