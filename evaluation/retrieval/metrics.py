"""Deterministic retrieval metrics."""

from __future__ import annotations

from collections.abc import Sequence


def hit_rate_at_k(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: Sequence[str],
    *,
    k: int,
) -> float:
    """Return 1 when any relevant chunk appears in the first ``k`` results."""
    _validate_k(k)
    relevant = set(relevant_chunk_ids)
    return float(any(chunk_id in relevant for chunk_id in retrieved_chunk_ids[:k]))


def recall_at_k(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: Sequence[str],
    *,
    k: int,
) -> float:
    """Return the fraction of relevant chunks retrieved in the first ``k`` results."""
    _validate_k(k)
    relevant = set(relevant_chunk_ids)
    if not relevant:
        raise ValueError("relevant_chunk_ids must not be empty")
    retrieved = set(retrieved_chunk_ids[:k])
    return len(relevant & retrieved) / len(relevant)


def reciprocal_rank(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: Sequence[str],
) -> float:
    """Return the reciprocal rank of the first relevant result, or zero."""
    relevant = set(relevant_chunk_ids)
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in relevant:
            return 1.0 / rank
    return 0.0


def _validate_k(k: int) -> None:
    if k <= 0:
        raise ValueError("k must be greater than zero")
