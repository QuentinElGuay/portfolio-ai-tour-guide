"""Ranking-fusion algorithms used by hybrid search."""

from collections.abc import Iterable
from dataclasses import dataclass

from .models import ScoreKind, SearchMetadata, SearchResult


@dataclass(frozen=True, slots=True)
class _ChunkIdentity:
    document_id: int
    chunk_id: str


@dataclass(slots=True)
class _FusionCandidate:
    result: SearchResult
    score: float = 0.0


def reciprocal_rank_fusion(
    rankings: Iterable[tuple[list[SearchResult], float]],
    *,
    k: int,
    rank_constant: int,
) -> list[SearchResult]:
    """Combine ranked results with weighted reciprocal-rank fusion."""
    candidates: dict[_ChunkIdentity, _FusionCandidate] = {}

    for ranking, weight in rankings:
        for rank, result in enumerate(ranking, start=1):
            identity = _ChunkIdentity(
                result.chunk.document_id,
                result.chunk.chunk_id,
            )
            candidate = candidates.setdefault(
                identity,
                _FusionCandidate(result=result),
            )
            candidate.score += weight / (rank_constant + rank)

    ordered = sorted(candidates.values(), key=lambda item: item.score, reverse=True)

    return [
        SearchResult(
            chunk=candidate.result.chunk,
            search=SearchMetadata(
                rank=rank,
                score=candidate.score,
                score_kind=ScoreKind.RRF,
            ),
        )
        for rank, candidate in enumerate(ordered[:k], start=1)
    ]


__all__ = ['reciprocal_rank_fusion']
