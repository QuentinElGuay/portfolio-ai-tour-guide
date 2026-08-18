"""Shared helpers for evaluation metric aggregation."""

from collections.abc import Iterable


def mean(values: Iterable[float]) -> float:
    """Return the arithmetic mean, or zero when there are no values."""
    values = list(values)
    return sum(values) / len(values) if values else 0.0


__all__ = ['mean']
