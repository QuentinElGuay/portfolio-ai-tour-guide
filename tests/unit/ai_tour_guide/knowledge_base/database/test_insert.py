"""Tests for transactional persistence operations."""

from unittest.mock import MagicMock, patch

import pytest

from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.ingestion.config import ChunkingConfig
from ai_tour_guide.knowledge_base.database import insert
from ai_tour_guide.knowledge_base.database.models import EmbeddingModelRow


def _embedding_metadata() -> EmbeddingMetadata:
    return EmbeddingMetadata(
        provider='test', model_name='model', dimensions=2, normalized=True
    )


def test_get_or_create_embedding_model_returns_compatible_existing_row() -> None:
    """Verify that compatible existing embedding metadata is reused."""
    session = MagicMock()
    existing = MagicMock(spec=EmbeddingModelRow)
    existing.dimensions = 2
    existing.normalized = True
    existing.distance_metric = 'cosine'
    session.scalar.return_value = existing

    assert (
        insert.get_or_create_embedding_model(session, _embedding_metadata()) is existing
    )
    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_get_or_create_embedding_model_rejects_incompatible_existing_row() -> None:
    """Verify that incompatible persisted embedding settings fail fast."""
    session = MagicMock()
    existing = MagicMock(spec=EmbeddingModelRow)
    existing.dimensions = 3
    existing.normalized = True
    existing.distance_metric = 'cosine'
    session.scalar.return_value = existing

    with pytest.raises(insert.EmbeddingModelConfigurationError):
        insert.get_or_create_embedding_model(session, _embedding_metadata())


def test_insert_document_rejects_duplicate_source_identity() -> None:
    """Verify that duplicate source identities do not create a replacement aggregate."""
    session = MagicMock()
    session.scalar.return_value = 1
    document = MagicMock()
    document.metadata.source_url = 'https://example.test/guide.pdf'
    document.version = None

    with (
        patch.object(insert.ModelFactory, 'create_document') as create_document,
        pytest.raises(insert.DocumentAlreadyExistsError),
    ):
        insert.insert_document(
            session,
            document,
            [MagicMock()],
            ChunkingConfig(100, 200, None, None),
            embedding_model_id=1,
        )

    create_document.assert_not_called()


def test_insert_document_replaces_duplicate_when_requested() -> None:
    """Verify that force mode removes the old aggregate before inserting its replacement."""
    session = MagicMock()
    existing = MagicMock()
    session.scalar.return_value = existing
    document = MagicMock()
    document.metadata.source_url = 'https://example.test/guide.pdf'
    document.version = None
    replacement = MagicMock()

    with patch.object(insert.ModelFactory, 'create_document', return_value=replacement):
        result = insert.insert_document(
            session,
            document,
            [MagicMock()],
            ChunkingConfig(100, 200, None, None),
            embedding_model_id=1,
            replace_existing=True,
        )

    assert result is replacement
    session.delete.assert_called_once_with(existing)
    assert session.flush.call_count == 2


@patch('ai_tour_guide.knowledge_base.database.insert.insert_document')
@patch('ai_tour_guide.knowledge_base.database.insert.get_or_create_embedding_model')
@patch('ai_tour_guide.knowledge_base.database.insert.Session')
@patch('ai_tour_guide.knowledge_base.database.insert.create_database_engine')
def test_insert_document_with_chunks_is_atomic_and_disposes_engine(
    create_database_engine: MagicMock,
    session_class: MagicMock,
    get_or_create: MagicMock,
    insert_document: MagicMock,
) -> None:
    """Verify that model and document writes share one transaction and dispose the engine."""
    engine = create_database_engine.return_value
    session = session_class.return_value.__enter__.return_value
    embedding_model = get_or_create.return_value
    embedding_model.embedding_model_id = 3
    inserted = insert_document.return_value
    inserted.document_id = 9

    result = insert.insert_document_with_chunks(
        MagicMock(),
        [MagicMock()],
        ChunkingConfig(100, 200, None, None),
        _embedding_metadata(),
    )

    assert result == 9
    session.begin.assert_called_once_with()
    get_or_create.assert_called_once_with(session, _embedding_metadata())
    assert insert_document.call_args.kwargs['embedding_model_id'] == 3
    engine.dispose.assert_called_once_with()
