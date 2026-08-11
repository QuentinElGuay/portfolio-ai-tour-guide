"""Dense-vector and full-text retrieval for stored document chunks."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.knowledge_base.models import (
    DocumentChunkRow,
    DocumentRow,
    EmbeddingModelRow,
)


@dataclass(frozen=True, slots=True)
class ScoredDocumentChunk:
    """A document chunk paired with its raw search score."""

    chunk: DocumentChunkRow
    score: float


type SearchResults = list[ScoredDocumentChunk]


def search_vector(
    session: Session,
    query: Sequence[float],
    k: int,
    *,
    embedding_metadata: EmbeddingMetadata,
) -> SearchResults:
    """Return nearest chunks and their raw vector distances.

    The embedding metadata prevents comparisons across incompatible vector
    spaces. The query embedding must have the matching dimensions and
    normalization.
    """
    _validate_k(k)

    query_embedding = list(query)
    if not query_embedding:
        raise ValueError('query embedding must not be empty')

    statement = _vector_statement(
        query_embedding,
        k,
        embedding_metadata=embedding_metadata,
    )
    return _execute_scored_search(session, statement)


def search_text(
    session: Session,
    query: str,
    k: int,
) -> SearchResults:
    """Return full-text matches together with their PostgreSQL text ranks."""
    _validate_k(k)
    if not query.strip():
        raise ValueError('query must not be blank')

    statement = _text_statement(query, k)
    return _execute_scored_search(session, statement)


def _execute_scored_search(session: Session, statement) -> SearchResults:
    """Execute a ranked statement and normalize its score column."""
    return [
        ScoredDocumentChunk(chunk=chunk, score=float(score))
        for chunk, score in session.execute(statement).all()
    ]


def _vector_statement(
    query: list[float],
    k: int,
    *,
    embedding_metadata: EmbeddingMetadata,
):
    distance = _vector_distance(query, embedding_metadata.distance_metric)
    return (
        select(DocumentChunkRow, distance.label('score'))
        .join(DocumentChunkRow.document)
        .join(DocumentRow.embedding_model)
        .where(DocumentChunkRow.embedding.is_not(None))
        .where(
            EmbeddingModelRow.provider == embedding_metadata.provider,
            EmbeddingModelRow.model_name == embedding_metadata.model_name,
            EmbeddingModelRow.model_revision == embedding_metadata.model_revision,
            EmbeddingModelRow.dimensions == embedding_metadata.dimensions,
            EmbeddingModelRow.normalized == embedding_metadata.normalized,
            EmbeddingModelRow.distance_metric == embedding_metadata.distance_metric,
        )
        .order_by(distance)
        .limit(k)
    )


def _text_statement(query: str, k: int):
    tsquery = func.plainto_tsquery('english', query)
    rank = func.ts_rank_cd(DocumentChunkRow.search_vector, tsquery)
    return (
        select(DocumentChunkRow, rank.label('score'))
        .where(DocumentChunkRow.search_vector.op('@@')(tsquery))
        .order_by(rank.desc())
        .limit(k)
    )


def _validate_k(k: int) -> None:
    """Validate the requested result count."""
    if k <= 0:
        raise ValueError('k must be greater than zero')


def _vector_distance(query: list[float], distance_metric: str):
    """Build the pgvector distance expression configured for the embedding model."""
    if distance_metric == 'cosine':
        return DocumentChunkRow.embedding.cosine_distance(query)
    if distance_metric == 'l2':
        return DocumentChunkRow.embedding.l2_distance(query)
    if distance_metric == 'inner_product':
        return DocumentChunkRow.embedding.max_inner_product(query)
    raise ValueError(f'Unsupported embedding distance metric {distance_metric!r}')


__all__ = [
    'ScoredDocumentChunk',
    'SearchResults',
    'search_text',
    'search_vector',
]
