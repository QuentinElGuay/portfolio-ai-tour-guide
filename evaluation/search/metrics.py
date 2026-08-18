"""Deterministic retrieval metrics."""

from collections.abc import Sequence


def hit_rate_at_k(
    retrieved_evidence: Sequence[str],
    relevant_evidence: Sequence[str],
    *,
    k: int,
) -> float:
    """Return 1 when any relevant evidence appears in the first ``k`` results."""
    _validate_k(k)
    relevant = set(relevant_evidence)
    return float(any(item in relevant for item in retrieved_evidence[:k]))


def recall_at_k(
    retrieved_evidence: Sequence[str],
    relevant_evidence: Sequence[str],
    *,
    k: int,
) -> float:
    """Return the fraction of relevant evidence retrieved in the first ``k`` results."""
    _validate_k(k)
    relevant = set(relevant_evidence)
    if not relevant:
        raise ValueError('relevant_evidence must not be empty')
    retrieved = set(retrieved_evidence[:k])
    return len(relevant & retrieved) / len(relevant)


def reciprocal_rank(
    retrieved_evidence: Sequence[str],
    relevant_evidence: Sequence[str],
) -> float:
    """Return the reciprocal rank of the first relevant result, or zero."""
    relevant = set(relevant_evidence)
    for rank, item in enumerate(retrieved_evidence, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def _validate_k(k: int) -> None:
    if k <= 0:
        raise ValueError('k must be greater than zero')
