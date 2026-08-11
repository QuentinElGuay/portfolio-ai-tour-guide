import os
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from ai_tour_guide.ingestion.artifacts import ChunkingMetadata

os.environ.setdefault('EMBEDDING_DIMENSIONS', '384')
os.environ.setdefault('EMBEDDING_MODEL_NAME', 'test-model')

from ai_tour_guide.domain.chunks import Chunk, EmbeddedChunk
from ai_tour_guide.domain.documents import DocumentMetadata, DocumentRecord
from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.knowledge_base.init_db import initialize_database
from ai_tour_guide.knowledge_base.insert import (
    DocumentAlreadyExistsError,
    EmbeddingModelConfigurationError,
    get_or_create_embedding_model,
    insert_document,
)
from ai_tour_guide.knowledge_base.models import EmbeddingModelRow


def _document_record(*, collection: str | None = None) -> DocumentRecord:
    return DocumentRecord(
        metadata=DocumentMetadata(
            title='A guide to Brittany',
            source_url='https://example.com/brittany',
            publisher='Tourism Board',
            publication_date=date(2026, 1, 2),
            authors=('Ada',),
            subject='Travel',
            keywords=('Brittany',),
            creator=None,
            producer=None,
            format='application/pdf',
            creation_date=datetime(2026, 1, 2, tzinfo=UTC),
            modification_date=None,
            source_page_count=12,
            page_count=11,
        ),
        source_checksum='document-sha256',
        collection=collection,
    )


def _chunking_metadata() -> ChunkingMetadata:
    return ChunkingMetadata(target_chars=750, max_chars=1_000)


def _embedded_chunk() -> EmbeddedChunk:
    return EmbeddedChunk(
        chunk=Chunk(
            chunk_id='chunk-0001',
            document_title='A guide to Brittany',
            section_path=('Coast',),
            text='Visit the coast.',
            embedding_text='Coast\n\nVisit the coast.',
            page_start=2,
            page_end=2,
            chunk_index=0,
            character_count=16,
        ),
        embedding=(0.1, 0.2, 0.3),
        embedding_input_sha256='embedding-sha256',
    )


def _embedding_metadata() -> EmbeddingMetadata:
    return EmbeddingMetadata(
        provider='fastembed',
        model_name='BAAI/bge-small-en-v1.5',
        dimensions=384,
        normalized=True,
    )


def test_insert_document_rejects_an_existing_document_without_changes() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = 42

    with pytest.raises(DocumentAlreadyExistsError, match='already exists'):
        insert_document(
            session,
            _document_record(),
            [_embedded_chunk()],
            _chunking_metadata(),
            embedding_model_id=7,
        )

    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_insert_document_rejects_a_document_without_chunks() -> None:
    session = MagicMock(spec=Session)

    with pytest.raises(ValueError, match='at least one embedded chunk'):
        insert_document(
            session,
            _document_record(),
            [],
            _chunking_metadata(),
            embedding_model_id=7,
        )

    session.scalar.assert_not_called()
    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_insert_document_adds_the_complete_aggregate() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    row = insert_document(
        session,
        _document_record(collection='tour-guides'),
        [_embedded_chunk()],
        _chunking_metadata(),
        embedding_model_id=7,
    )

    assert row.collection == 'tour-guides'
    assert row.embedding_model_id == 7
    assert len(row.chunks) == 1
    assert row.embedded_at.tzinfo is UTC
    session.add.assert_called_once_with(row)
    session.flush.assert_called_once_with()


def test_get_or_create_embedding_model_reuses_matching_configuration() -> None:
    existing = EmbeddingModelRow(
        embedding_model_id=7,
        provider='fastembed',
        model_name='BAAI/bge-small-en-v1.5',
        model_revision='default',
        dimensions=384,
        normalized=True,
        distance_metric='cosine',
    )
    session = MagicMock(spec=Session)
    session.scalar.return_value = existing

    result = get_or_create_embedding_model(session, _embedding_metadata())

    assert result is existing
    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_get_or_create_embedding_model_adds_all_required_configuration() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    result = get_or_create_embedding_model(session, _embedding_metadata())

    assert result.provider == 'fastembed'
    assert result.model_name == 'BAAI/bge-small-en-v1.5'
    assert result.model_revision == 'default'
    assert result.dimensions == 384
    assert result.normalized is True
    assert result.distance_metric == 'cosine'
    session.add.assert_called_once_with(result)
    session.flush.assert_called_once_with()


def test_get_or_create_embedding_model_rejects_changed_dimensions() -> None:
    existing = EmbeddingModelRow(
        embedding_model_id=7,
        provider='fastembed',
        model_name='BAAI/bge-small-en-v1.5',
        model_revision='default',
        dimensions=768,
        normalized=True,
        distance_metric='cosine',
    )
    session = MagicMock(spec=Session)
    session.scalar.return_value = existing

    with pytest.raises(EmbeddingModelConfigurationError, match='does not match'):
        get_or_create_embedding_model(session, _embedding_metadata())

    session.add.assert_not_called()
    session.flush.assert_not_called()


@patch('ai_tour_guide.knowledge_base.init_db.metadata')
@patch('ai_tour_guide.knowledge_base.init_db.create_database_engine')
def test_initialize_database_creates_missing_indexes(
    create_engine: MagicMock,
    metadata: MagicMock,
) -> None:
    engine = MagicMock()
    connection = MagicMock()
    create_engine.return_value = engine
    engine.begin.return_value.__enter__.return_value = connection
    index = MagicMock()
    table = MagicMock()
    table.indexes = [index]
    metadata.tables.values.return_value = [table]

    initialize_database()

    metadata.create_all.assert_called_once_with(bind=connection, checkfirst=True)
    index.create.assert_called_once_with(bind=connection, checkfirst=True)
    engine.dispose.assert_called_once_with()
