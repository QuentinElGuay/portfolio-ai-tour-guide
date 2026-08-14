from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from ai_tour_guide.embedding.fastembed import FastEmbedder
from ai_tour_guide.embedding.settings import EmbeddingSettings
from ai_tour_guide.knowledge_base.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.retrieval import SearchMode
from ai_tour_guide.knowledge_base.retrieval_models import (
    HybridSearchSettings,
    RetrievedChunk,
    ScoreKind,
    SourceMetadata,
)
from ai_tour_guide.knowledge_base.search import search_text, search_vector


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


class SearchStrategy(Protocol):
    def search(
        self,
        session: Session,
        query: str,
        *,
        k: int,
    ) -> list[RetrievedChunk]: ...


class TextSearchStrategy:
    def search(
        self,
        session: Session,
        query: str,
        *,
        k: int,
    ) -> list[RetrievedChunk]:
        results = search_text(session, query, k)

        return [
            RetrievedChunk(
                chunk=result.chunk,
                rank=rank,
                score=result.score,
                score_kind=ScoreKind.TEXT_RANK,
                source=_create_source_metadata(result.chunk),
            )
            for rank, result in enumerate(results, start=1)
        ]


class VectorSearchStrategy:
    def __init__(self, embedder: FastEmbedder) -> None:
        self.embedder = embedder

    def search(
        self,
        session: Session,
        query: str,
        *,
        k: int,
    ) -> list[RetrievedChunk]:
        query_embedding = self.embedder.embed_query(query).tolist()

        results = search_vector(
            session,
            query_embedding,
            k,
            embedding_metadata=self.embedder.metadata,
        )

        score_kind = _score_kind(self.embedder.metadata.distance_metric)

        return [
            RetrievedChunk(
                chunk=result.chunk,
                rank=rank,
                score=_relevance_score(
                    result.score,
                    self.embedder.metadata.distance_metric,
                ),
                score_kind=score_kind,
                source=_create_source_metadata(result.chunk),
            )
            for rank, result in enumerate(results, start=1)
        ]


class HybridSearchStrategy:
    def __init__(
        self,
        vector: SearchStrategy,
        text: SearchStrategy,
        settings: HybridSearchSettings,
    ) -> None:
        self.vector = vector
        self.text = text
        self.settings = settings

    def search(
        self,
        session: Session,
        query: str,
        *,
        k: int,
    ) -> list[RetrievedChunk]:
        vector_results = self.vector.search(
            session,
            query,
            k=k,
        )

        text_results = self.text.search(
            session,
            query,
            k=k,
        )

        return _fuse_rankings(
            [
                (vector_results, self.settings.vector_weight),
                (text_results, self.settings.text_weight),
            ],
            k=k,
            rank_constant=self.settings.rank_constant,
        )


def _create_search_strategy(
    mode: SearchMode,
    *,
    hybrid_settings: HybridSearchSettings | None = None,
) -> SearchStrategy:
    if mode is SearchMode.TEXT:
        return TextSearchStrategy()

    settings = EmbeddingSettings()
    embedder = FastEmbedder(
        model_name=settings.model_name,
        normalize=settings.normalize,
        cache_dir=settings.cache_dir,
    )

    vector_strategy = VectorSearchStrategy(embedder)

    if mode is SearchMode.VECTOR:
        return vector_strategy

    if mode is SearchMode.HYBRID:
        return HybridSearchStrategy(
            vector=vector_strategy,
            text=TextSearchStrategy(),
            settings=hybrid_settings or HybridSearchSettings(),
        )

    raise ValueError(f'Unsupported search mode: {mode}')


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


def _chunk_identity(chunk: DocumentChunkRow) -> _ChunkIdentity:
    """Return the database identity for a retrieved chunk."""
    document_id = getattr(chunk, 'document_id', None)
    if not isinstance(document_id, int):
        document_id = None
    return _ChunkIdentity(document_id=document_id, chunk_id=chunk.chunk_id)


def _score_kind(distance_metric: str) -> ScoreKind:
    if distance_metric == 'cosine':
        return ScoreKind.COSINE_SIMILARITY
    if distance_metric == 'l2':
        return ScoreKind.L2_RELEVANCE
    if distance_metric == 'inner_product':
        return ScoreKind.INNER_PRODUCT
    raise ValueError(f'Unsupported embedding distance metric {distance_metric!r}')


def _relevance_score(raw_score: float, distance_metric: str) -> float:
    """Convert a lower-is-better vector distance to a higher-is-better score."""
    if distance_metric == 'cosine':
        return 1.0 - raw_score
    if distance_metric in {'l2', 'inner_product'}:
        return -raw_score
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
