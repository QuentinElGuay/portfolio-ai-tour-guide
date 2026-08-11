"""Reusable retrieval orchestration for the knowledge base."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
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


class ScoreKind(StrEnum):
    """Meaning of a retrieval score."""

    COSINE_SIMILARITY = 'cosine_similarity'
    L2_RELEVANCE = 'l2_relevance'
    INNER_PRODUCT = 'inner_product'
    TEXT_RANK = 'text_rank'
    RRF = 'rrf'


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Stable provenance needed to identify and cite a retrieved chunk."""

    document_id: int
    chunk_id: str
    title: str
    source_url: str
    publisher: str | None
    publication_date: date | None
    collection: str | None
    version: str | None
    section_path: tuple[str, ...]
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A ranked chunk and the score that produced its position."""

    chunk: DocumentChunkRow
    rank: int
    score: float
    score_kind: ScoreKind
    source: SourceMetadata


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


def _create_source_metadata(chunk: DocumentChunkRow) -> SourceMetadata:
    """Copy source provenance while the ORM relationship is still attached."""
    document = chunk.document
    return SourceMetadata(
        document_id=chunk.document_id,
        chunk_id=chunk.chunk_id,
        title=document.title,
        source_url=document.source_url,
        publisher=document.publisher,
        publication_date=document.publication_date,
        collection=document.collection,
        version=document.version,
        section_path=tuple(chunk.section_path),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
    )


def _relevance_score(raw_score: float, distance_metric: str) -> float:
    """Convert a lower-is-better vector distance to a higher-is-better score."""
    if distance_metric == 'cosine':
        return 1.0 - raw_score
    if distance_metric in {'l2', 'inner_product'}:
        return -raw_score
    raise ValueError(f'Unsupported embedding distance metric {distance_metric!r}')


def _score_kind(distance_metric: str) -> ScoreKind:
    if distance_metric == 'cosine':
        return ScoreKind.COSINE_SIMILARITY
    if distance_metric == 'l2':
        return ScoreKind.L2_RELEVANCE
    if distance_metric == 'inner_product':
        return ScoreKind.INNER_PRODUCT
    raise ValueError(f'Unsupported embedding distance metric {distance_metric!r}')


def _fuse_rankings(
    rankings: Iterable[tuple[list[RetrievedChunk], float]],
    *,
    k: int,
    rank_constant: int,
) -> list[RetrievedChunk]:
    """Combine ranked results using reciprocal-rank fusion."""
    candidates: dict[_ChunkIdentity, _FusionCandidate] = {}
    for ranking, weight in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            identity = _chunk_identity(chunk.chunk)
            candidate = candidates.setdefault(
                identity,
                _FusionCandidate(chunk=chunk.chunk),
            )
            candidate.score += weight / (rank_constant + rank)

    ranked_candidates = sorted(
        candidates.values(),
        key=lambda candidate: candidate.score,
        reverse=True,
    )
    return [
        RetrievedChunk(
            chunk=candidate.chunk,
            rank=rank,
            score=candidate.score,
            score_kind=ScoreKind.RRF,
            source=_create_source_metadata(candidate.chunk),
        )
        for rank, candidate in enumerate(ranked_candidates[:k], start=1)
    ]


def retrieve(
    query: str,
    *,
    mode: SearchMode = 'vector',
    k: int = 5,
    hybrid_settings: HybridSearchSettings | None = None,
) -> list[RetrievedChunk]:
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
                vector_results = search_vector(
                    session,
                    query_embedding,
                    k,
                    embedding_metadata=embedder.metadata,
                )
                vector_score_kind = _score_kind(embedder.metadata.distance_metric)
                vector_chunks = [
                    RetrievedChunk(
                        chunk=result.chunk,
                        rank=rank,
                        score=_relevance_score(
                            result.score,
                            embedder.metadata.distance_metric,
                        ),
                        score_kind=vector_score_kind,
                        source=_create_source_metadata(result.chunk),
                    )
                    for rank, result in enumerate(
                        vector_results,
                        start=1,
                    )
                ]

                if selected_mode is SearchMode.VECTOR:
                    return vector_chunks

                text_results = search_text(session, query, k)
                text_chunks = [
                    RetrievedChunk(
                        chunk=result.chunk,
                        rank=rank,
                        score=result.score,
                        score_kind=ScoreKind.TEXT_RANK,
                        source=_create_source_metadata(result.chunk),
                    )
                    for rank, result in enumerate(text_results, start=1)
                ]
                return _fuse_rankings(
                    [
                        (vector_chunks, selected_hybrid_settings.vector_weight),
                        (text_chunks, selected_hybrid_settings.text_weight),
                    ],
                    k=k,
                    rank_constant=selected_hybrid_settings.rank_constant,
                )

            text_results = search_text(session, query, k)
            return [
                RetrievedChunk(
                    chunk=result.chunk,
                    rank=rank,
                    score=result.score,
                    score_kind=ScoreKind.TEXT_RANK,
                    source=_create_source_metadata(result.chunk),
                )
                for rank, result in enumerate(text_results, start=1)
            ]
    finally:
        engine.dispose()


__all__ = [
    'DEFAULT_RRF_RANK_CONSTANT',
    'HybridSearchSettings',
    'RetrievedChunk',
    'ScoreKind',
    'SearchMode',
    'SourceMetadata',
    'retrieve',
]
