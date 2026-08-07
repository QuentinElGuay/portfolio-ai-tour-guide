import os
from datetime import UTC, date, datetime

from sqlalchemy import inspect

from ai_tour_guide.ingestion.artifacts import ChunkingMetadata

os.environ.setdefault('EMBEDDING_DIMENSIONS', '384')

from ai_tour_guide.database.models import (
    DocumentChunkRow,
    DocumentRow,
    ModelFactory,
)
from ai_tour_guide.domain.chunks import Chunk, EmbeddedChunk
from ai_tour_guide.domain.documents import (
    DocumentMetadata,
    DocumentRecord,
)


def _document_record(
    *,
    collection: str | None = 'tour-guides',
) -> DocumentRecord:
    return DocumentRecord(
        metadata=DocumentMetadata(
            title='A guide to Brittany',
            source_url='https://example.com/brittany.pdf',
            publisher='Tourism Board',
            publication_date=date(2026, 1, 2),
            authors=('Ada', 'Grace'),
            subject='Travel',
            keywords=('Brittany', 'France'),
            creator='Writer',
            producer='PDF tool',
            format='PDF 1.7',
            creation_date=datetime(2026, 1, 2, tzinfo=UTC),
            modification_date=datetime(2026, 1, 3, tzinfo=UTC),
            source_page_count=12,
            page_count=11,
        ),
        source_checksum='document-sha256',
        collection=collection,
        version='2026',
    )


def _chunking_metadata() -> ChunkingMetadata:
    return ChunkingMetadata(target_chars=750, max_chars=1_000)


def _embedded_chunk() -> EmbeddedChunk:
    return EmbeddedChunk(
        chunk=Chunk(
            chunk_id='brittany:chunk-0001',
            document_title='A guide to Brittany',
            section_path=('Brittany', 'Coast'),
            text='Visit the coast.',
            embedding_text='Brittany\nCoast\n\nVisit the coast.',
            page_start=2,
            page_end=3,
            chunk_index=0,
            character_count=16,
        ),
        embedding=(0.1, 0.2, 0.3),
        embedding_input_sha256='embedding-sha256',
    )


def test_create_document_preserves_document_field_names() -> None:
    row = ModelFactory.create_document(
        _document_record(),
        embedding_model_id=7,
        chunking=_chunking_metadata(),
    )

    assert isinstance(row, DocumentRow)
    assert inspect(row).transient
    assert row.embedding_model_id == 7
    assert row.collection == 'tour-guides'
    assert row.version == '2026'
    assert row.title == 'A guide to Brittany'
    assert row.source_url == 'https://example.com/brittany.pdf'
    assert row.publication_date == date(2026, 1, 2)
    assert row.authors == ['Ada', 'Grace']
    assert row.keywords == ['Brittany', 'France']
    assert row.format == 'PDF 1.7'
    assert row.creation_date == datetime(2026, 1, 2, tzinfo=UTC)
    assert row.modification_date == datetime(2026, 1, 3, tzinfo=UTC)
    assert row.source_page_count == 12
    assert row.page_count == 11
    assert row.source_checksum == 'document-sha256'
    assert 'document_id' not in row.__dict__
    assert 'created_at' not in row.__dict__


def test_create_document_attaches_mapped_chunk_rows() -> None:
    row = ModelFactory.create_document(
        _document_record(),
        embedding_model_id=7,
        chunks=[_embedded_chunk()],
        chunking=_chunking_metadata(),
    )

    assert len(row.chunks) == 1
    chunk_row = row.chunks[0]
    assert isinstance(chunk_row, DocumentChunkRow)
    assert chunk_row.document is row
    assert chunk_row.chunk_id == 'brittany:chunk-0001'
    assert chunk_row.chunk_index == 0
    assert chunk_row.section_path == ['Brittany', 'Coast']
    assert chunk_row.text == 'Visit the coast.'
    assert chunk_row.embedding_text == 'Brittany\nCoast\n\nVisit the coast.'
    assert chunk_row.page_start == 2
    assert chunk_row.page_end == 3
    assert chunk_row.character_count == 16
    assert chunk_row.embedding_input_sha256 == 'embedding-sha256'
    assert chunk_row.embedding == [0.1, 0.2, 0.3]
    assert 'document_id' not in chunk_row.__dict__
    assert 'created_at' not in chunk_row.__dict__


def test_document_chunk_uses_document_scoped_composite_primary_key() -> None:
    primary_key_columns = tuple(
        column.name for column in DocumentChunkRow.__table__.primary_key.columns
    )

    assert primary_key_columns == ('document_id', 'chunk_id')


def test_document_requires_an_embedding_model() -> None:
    assert DocumentRow.__table__.c.embedding_model_id.nullable is False


def test_document_collection_is_optional() -> None:
    row = ModelFactory.create_document(
        _document_record(collection=None),
        embedding_model_id=7,
        chunking=_chunking_metadata(),
    )

    assert row.collection is None
    assert DocumentRow.__table__.c.collection.nullable is True


def test_document_source_url_is_globally_unique() -> None:
    constraint = next(
        constraint
        for constraint in DocumentRow.__table__.constraints
        if constraint.name == 'uq_documents_source_url'
    )

    assert tuple(column.name for column in constraint.columns) == ('source_url',)
