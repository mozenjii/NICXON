"""Four-state values and Kleene logic.

docs/04_RULE_IR_SPEC.md forbids coercing a missing input to false or zero. That is easy
to state and easy to violate by accident, so UNKNOWN raises on __bool__: any code that
writes `if value:` over a possibly-unknown value fails loudly instead of silently
treating it as false.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Union


class _Unknown:
    """The absence of a determination. Distinct from false, and from an error."""

    _instance: _Unknown | None = None

    def __new__(cls) -> _Unknown:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNKNOWN"

    def __bool__(self) -> bool:
        raise TypeError(
            "UNKNOWN has no truth value. Handle the unknown case explicitly — "
            "coercing it to false is what docs/04_RULE_IR_SPEC.md forbids."
        )


UNKNOWN = _Unknown()

Value = Union[bool, Decimal, int, str, None, _Unknown]


def is_unknown(v: Value) -> bool:
    return isinstance(v, _Unknown)


def kleene_all(values: list[Value]) -> Value:
    """Conjunction. One false settles it even when others are unknown."""
    if any(v is False for v in values):
        return False
    if any(is_unknown(v) for v in values):
        return UNKNOWN
    return True


def kleene_any(values: list[Value]) -> Value:
    """Disjunction. One true settles it even when others are unknown."""
    if any(v is True for v in values):
        return True
    if any(is_unknown(v) for v in values):
        return UNKNOWN
    return False


def kleene_not(v: Value) -> Value:
    if is_unknown(v):
        return UNKNOWN
    if isinstance(v, bool):
        return not v
    raise TypeError(f"not: expected boolean or UNKNOWN, got {type(v).__name__}")
