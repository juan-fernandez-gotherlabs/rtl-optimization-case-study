"""Minimal compatibility exports for the standalone evaluator snapshot."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def register_domain(_name: str) -> Callable[[T], T]:
    """Preserve the original domain decorator without requiring Evölther."""

    def decorator(value: T) -> T:
        return value

    return decorator
