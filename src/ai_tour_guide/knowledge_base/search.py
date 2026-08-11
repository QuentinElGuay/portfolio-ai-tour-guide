"""Dense-vector and full-text retrieval for stored document chunks."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.knowledge_base.models import (
    DocumentChunkRow,
    DocumentRow,
    EmbeddingModelRow,
)


def search_vector(
    session: Session,
    query: Sequence[float],
    k: int,
    *,
    embedding_metadata: EmbeddingMetadata,
) -> list[DocumentChunkRow]:
    """Return nearest chunks embedded with the same model as the query.

    The embedding metadata prevents comparisons across incompatible vector
    spaces. The query embedding must have the matching dimensions and
    normalization.
    """
    _validate_k(k)

    query_embedding = list(query)
    if not query_embedding:
        raise ValueError('query embedding must not be empty')

    distance = _vector_distance(query_embedding, embedding_metadata.distance_metric)
    statement = (
        select(DocumentChunkRow)
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
    return list(session.scalars(statement))


def search_text(
    session: Session,
    query: str,
    k: int,
) -> list[DocumentChunkRow]:
    """Return the ``k`` best full-text matches for an English-language query."""
    _validate_k(k)
    if not query.strip():
        raise ValueError('query must not be blank')

    tsquery = func.plainto_tsquery('english', query)
    rank = func.ts_rank_cd(DocumentChunkRow.search_vector, tsquery)
    statement = (
        select(DocumentChunkRow)
        .where(DocumentChunkRow.search_vector.op('@@')(tsquery))
        .order_by(rank.desc())
        .limit(k)
    )
    return list(session.scalars(statement))


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


__all__ = ['search_text', 'search_vector']
