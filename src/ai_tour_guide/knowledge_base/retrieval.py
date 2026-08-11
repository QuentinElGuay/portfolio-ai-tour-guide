"""Reusable retrieval orchestration for the knowledge base."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from sqlalchemy.orm import Session

from ai_tour_guide.embedding import FastEmbedder
from ai_tour_guide.embedding.settings import EmbeddingSettings
from ai_tour_guide.knowledge_base.connection import create_database_engine
from ai_tour_guide.knowledge_base.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.search import search_text, search_vector


class SearchMode(StrEnum):
    """Supported knowledge-base retrieval strategies."""

    VECTOR = 'vector'
    TEXT = 'text'
    HYBRID = 'hybrid'


DEFAULT_RRF_RANK_CONSTANT = 60


@dataclass(frozen=True, slots=True)
class HybridSearchSettings:
    """Configuration for combining vector and full-text rankings."""

    vector_weight: float = 1.0
    text_weight: float = 1.0
    rank_constant: int = DEFAULT_RRF_RANK_CONSTANT

    def __post_init__(self) -> None:
        if self.vector_weight < 0 or not isfinite(self.vector_weight):
            raise ValueError('vector_weight must be a finite non-negative number')
        if self.text_weight < 0 or not isfinite(self.text_weight):
            raise ValueError('text_weight must be a finite non-negative number')
        if self.vector_weight == 0 and self.text_weight == 0:
            raise ValueError(
                'at least one hybrid search weight must be greater than zero'
            )
        if self.rank_constant < 0:
            raise ValueError('rank_constant must be non-negative')


@dataclass(frozen=True, slots=True)
class _ChunkIdentity:
    """Identity used to deduplicate chunks across retrieval strategies."""

    document_id: int | None
    chunk_id: str


@dataclass(slots=True)
class _FusionCandidate:
    """A chunk and its accumulated reciprocal-rank fusion score."""

    chunk: DocumentChunkRow
    score: float = 0.0


def _chunk_identity(chunk: DocumentChunkRow) -> _ChunkIdentity:
    """Return the database identity for a retrieved chunk."""
    document_id = getattr(chunk, 'document_id', None)
    if not isinstance(document_id, int):
        document_id = None
    return _ChunkIdentity(document_id=document_id, chunk_id=chunk.chunk_id)


def _fuse_rankings(
    rankings: Iterable[tuple[list[DocumentChunkRow], float]],
    *,
    k: int,
    rank_constant: int,
) -> list[DocumentChunkRow]:
    """Combine ranked results using reciprocal-rank fusion."""
    candidates: dict[_ChunkIdentity, _FusionCandidate] = {}
    for ranking, weight in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            identity = _chunk_identity(chunk)
            candidate = candidates.setdefault(
                identity,
                _FusionCandidate(chunk=chunk),
            )
            candidate.score += weight / (rank_constant + rank)

    ranked_candidates = sorted(
        candidates.values(),
        key=lambda candidate: candidate.score,
        reverse=True,
    )
    return [candidate.chunk for candidate in ranked_candidates[:k]]


def retrieve(
    query: str,
    *,
    mode: SearchMode = 'vector',
    k: int = 5,
    hybrid_settings: HybridSearchSettings | None = None,
) -> list[DocumentChunkRow]:
    """Retrieve ranked document chunks using the selected search mode.

    This function owns the database, session, and embedding lifecycle so
    callers only need to choose a query, search mode, and result count.
    """
    try:
        selected_mode = SearchMode(mode)
    except ValueError as exc:
        choices = ', '.join(search_mode.value for search_mode in SearchMode)
        raise ValueError(
            f'Unsupported search mode: {mode!r}. Choose one of: {choices}'
        ) from exc
    if selected_mode is SearchMode.HYBRID:
        selected_hybrid_settings = hybrid_settings or HybridSearchSettings()
    else:
        selected_hybrid_settings = None

    engine = create_database_engine()

    try:
        with Session(engine) as session:
            if selected_mode in (SearchMode.VECTOR, SearchMode.HYBRID):
                settings = EmbeddingSettings()
                embedder = FastEmbedder(
                    model_name=settings.model_name,
                    normalize=settings.normalize,
                    cache_dir=settings.cache_dir,
                )
                query_embedding = embedder.embed_query(query).tolist()
                vector_chunks = search_vector(
                    session,
                    query_embedding,
                    k,
                    embedding_metadata=embedder.metadata,
                )

                if selected_mode is SearchMode.VECTOR:
                    return vector_chunks

                text_chunks = search_text(session, query, k)
                return _fuse_rankings(
                    [
                        (vector_chunks, selected_hybrid_settings.vector_weight),
                        (text_chunks, selected_hybrid_settings.text_weight),
                    ],
                    k=k,
                    rank_constant=selected_hybrid_settings.rank_constant,
                )

            return search_text(session, query, k)
    finally:
        engine.dispose()


__all__ = [
    'DEFAULT_RRF_RANK_CONSTANT',
    'HybridSearchSettings',
    'SearchMode',
    'retrieve',
]
