"""Search Strategy implementations for text, vector, and hybrid ranking."""

from typing import Protocol

from sqlalchemy.orm import Session

from ai_tour_guide.embedding.fastembed import FastEmbedder
from ai_tour_guide.embedding.settings import EmbeddingSettings

from .fusion import reciprocal_rank_fusion
from .models import (
    HybridSearchSettings,
    ScoreKind,
    SearchMetadata,
    SearchMode,
    SearchResult,
)
from .queries import search_text, search_vector


class SearchStrategy(Protocol):
    """Structural interface implemented by all ranking strategies."""

    def search(self, session: Session, query: str, *, k: int) -> list[SearchResult]: ...


class TextSearchStrategy:
    """Rank chunks using PostgreSQL full-text search."""

    def search(self, session: Session, query: str, *, k: int) -> list[SearchResult]:
        return [
            SearchResult(
                chunk=result.chunk,
                search=SearchMetadata(
                    rank=rank,
                    score=result.score,
                    score_kind=ScoreKind.TEXT_RANK,
                ),
            )
            for rank, result in enumerate(search_text(session, query, k), start=1)
        ]


class VectorSearchStrategy:
    """Embed the query and rank chunks in the configured vector space."""

    def __init__(self, embedder: FastEmbedder) -> None:
        self.embedder = embedder

    def search(self, session: Session, query: str, *, k: int) -> list[SearchResult]:
        query_embedding = self.embedder.embed_query(query).tolist()
        score_kind = _score_kind(self.embedder.metadata.distance_metric)
        return [
            SearchResult(
                chunk=result.chunk,
                search=SearchMetadata(
                    rank=rank,
                    score=_relevance_score(
                        result.score,
                        self.embedder.metadata.distance_metric,
                    ),
                    score_kind=score_kind,
                ),
            )
            for rank, result in enumerate(
                search_vector(
                    session,
                    query_embedding,
                    k,
                    embedding_metadata=self.embedder.metadata,
                ),
                start=1,
            )
        ]


class HybridSearchStrategy:
    """Compose vector and text strategies and fuse their rankings."""

    def __init__(
        self,
        vector: SearchStrategy,
        text: SearchStrategy,
        settings: HybridSearchSettings,
    ) -> None:
        self.vector = vector
        self.text = text
        self.settings = settings

    def search(self, session: Session, query: str, *, k: int) -> list[SearchResult]:
        vector_results = self.vector.search(session, query, k=k)
        text_results = self.text.search(session, query, k=k)
        return reciprocal_rank_fusion(
            [
                (vector_results, self.settings.vector_weight),
                (text_results, self.settings.text_weight),
            ],
            k=k,
            rank_constant=self.settings.rank_constant,
        )


def create_search_strategy(
    mode: SearchMode,
    *,
    hybrid_settings: HybridSearchSettings | None = None,
) -> SearchStrategy:
    """Build the concrete strategy selected by ``mode``."""
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


def _score_kind(distance_metric: str) -> ScoreKind:
    if distance_metric == 'cosine':
        return ScoreKind.COSINE_SIMILARITY
    if distance_metric == 'l2':
        return ScoreKind.L2_RELEVANCE
    if distance_metric == 'inner_product':
        return ScoreKind.INNER_PRODUCT
    raise ValueError(f'Unsupported embedding distance metric {distance_metric!r}')


def _relevance_score(raw_score: float, distance_metric: str) -> float:
    if distance_metric == 'cosine':
        return 1.0 - raw_score
    if distance_metric in {'l2', 'inner_product'}:
        return -raw_score
    raise ValueError(f'Unsupported embedding distance metric {distance_metric!r}')


__all__ = [
    'HybridSearchStrategy',
    'SearchStrategy',
    'TextSearchStrategy',
    'VectorSearchStrategy',
    'create_search_strategy',
]
