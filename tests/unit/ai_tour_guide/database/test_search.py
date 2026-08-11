import os
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

os.environ.setdefault('EMBEDDING_DIMENSIONS', '384')
os.environ.setdefault('EMBEDDING_MODEL_NAME', 'test-model')

from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.knowledge_base.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.search import (
    ScoredDocumentChunk,
    search_text,
    search_vector,
)


def _embedding_metadata(*, distance_metric: str = 'cosine') -> EmbeddingMetadata:
    return EmbeddingMetadata(
        provider='fastembed',
        model_name='BAAI/bge-small-en-v1.5',
        dimensions=384,
        normalized=True,
        distance_metric=distance_metric,
    )


def test_search_vector_returns_ranked_chunks() -> None:
    chunk = MagicMock(spec=DocumentChunkRow)
    session = MagicMock(spec=Session)
    session.execute.return_value.all.return_value = [(chunk, 0.2)]

    result = search_vector(
        session,
        [0.1, 0.2, 0.3],
        k=1,
        embedding_metadata=_embedding_metadata(),
    )

    assert result == [ScoredDocumentChunk(chunk=chunk, score=0.2)]
    session.execute.assert_called_once()
    statement = session.execute.call_args.args[0]
    statement_sql = str(statement)
    assert 'JOIN documents' in statement_sql
    assert 'JOIN embedding_models' in statement_sql
    assert 'embedding_models.provider' in statement_sql


def test_search_text_returns_ranked_chunks() -> None:
    chunk = MagicMock(spec=DocumentChunkRow)
    session = MagicMock(spec=Session)
    session.execute.return_value.all.return_value = [(chunk, 0.7)]

    result = search_text(session, 'Brittany coast', k=1)

    assert result == [ScoredDocumentChunk(chunk=chunk, score=0.7)]
    session.execute.assert_called_once()


@pytest.mark.parametrize('search', [search_vector, search_text])
def test_search_rejects_non_positive_k(search) -> None:
    session = MagicMock(spec=Session)
    query = [0.1] if search is search_vector else 'Brittany'
    kwargs = (
        {'embedding_metadata': _embedding_metadata()} if search is search_vector else {}
    )

    with pytest.raises(ValueError, match='k must be greater than zero'):
        search(session, query, k=0, **kwargs)

    session.execute.assert_not_called()


def test_search_vector_rejects_an_empty_embedding() -> None:
    session = MagicMock(spec=Session)

    with pytest.raises(ValueError, match='must not be empty'):
        search_vector(
            session,
            [],
            k=1,
            embedding_metadata=_embedding_metadata(),
        )

    session.execute.assert_not_called()


@pytest.mark.parametrize('distance_metric', ['l2', 'inner_product'])
def test_search_vector_supports_the_configured_distance_metric(
    distance_metric: str,
) -> None:
    session = MagicMock(spec=Session)
    session.execute.return_value.all.return_value = []

    search_vector(
        session,
        [0.1, 0.2, 0.3],
        k=1,
        embedding_metadata=_embedding_metadata(distance_metric=distance_metric),
    )

    session.execute.assert_called_once()


def test_search_text_rejects_a_blank_query() -> None:
    session = MagicMock(spec=Session)

    with pytest.raises(ValueError, match='must not be blank'):
        search_text(session, '  ', k=1)

    session.execute.assert_not_called()
