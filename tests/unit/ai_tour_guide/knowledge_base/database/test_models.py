"""Tests for ORM mappings and ModelFactory."""

from datetime import UTC, date, datetime

from ai_tour_guide.domain.chunks import Chunk, EmbeddedChunk
from ai_tour_guide.domain.documents import DocumentMetadata, DocumentRecord
from ai_tour_guide.ingestion.config import ChunkingConfig
from ai_tour_guide.knowledge_base.database.models import (
    DocumentChunkRow,
    DocumentRow,
    EmbeddingModelRow,
    ModelFactory,
)
from ai_tour_guide.knowledge_base.database.tables import (
    document_chunks,
    documents,
    embedding_models,
)


def _embedded_chunk() -> EmbeddedChunk:
    chunk = Chunk(
        chunk_id='guide:chunk-0000',
        document_title='Guide',
        section_path=('Guide', 'Travel'),
        section_id='guide-travel',
        section_chunk_index=2,
        text='Travel by train.',
        embedding_text='Guide\nTravel\n\nTravel by train.',
        page_start=4,
        page_end=5,
        chunk_index=0,
        character_count=16,
    )
    return EmbeddedChunk(
        chunk=chunk, embedding=(0.1, 0.2), embedding_input_sha256='abc'
    )


def _document() -> DocumentRecord:
    return DocumentRecord(
        metadata=DocumentMetadata(
            title='Guide',
            source_url='https://example.test/guide.pdf',
            publisher='Test Press',
            publication_date=date(2026, 1, 1),
            authors=('Author',),
            subject='Travel',
            keywords=('Brittany',),
            creator='Creator',
            producer='Producer',
            format='PDF',
            creation_date=datetime(2026, 1, 1, tzinfo=UTC),
            modification_date=datetime(2026, 1, 2, tzinfo=UTC),
            source_page_count=10,
            page_count=9,
        ),
        source_checksum='source-sha256',
        collection='guides',
        version='2026',
    )


def test_orm_models_map_existing_core_tables() -> None:
    """Verify that ORM rows map to the Core tables rather than duplicate DDL."""
    assert EmbeddingModelRow.__table__ is embedding_models
    assert DocumentRow.__table__ is documents
    assert DocumentChunkRow.__table__ is document_chunks


def test_model_factory_creates_document_with_chunk_children() -> None:
    """Verify that document provenance, chunking settings, and children are preserved."""
    row = ModelFactory.create_document(
        _document(),
        embedding_model_id=7,
        chunking=ChunkingConfig(100, 200, 1, 3),
        chunks=[_embedded_chunk()],
    )

    assert row.embedding_model_id == 7
    assert row.source_checksum == 'source-sha256'
    assert row.collection == 'guides'
    assert row.version == '2026'
    assert (row.target_chunk_chars, row.max_chunk_chars) == (100, 200)
    assert len(row.chunks) == 1
    assert row.chunks[0].section_path == ['Guide', 'Travel']


def test_model_factory_creates_chunk_row() -> None:
    """Verify that chunk provenance and embeddings are converted for persistence."""
    row = ModelFactory.create_chunk(_embedded_chunk())

    assert row.chunk_id == 'guide:chunk-0000'
    assert row.section_id == 'guide-travel'
    assert row.section_chunk_index == 2
    assert row.page_start == 4 and row.page_end == 5
    assert row.embedding == [0.1, 0.2]
    assert row.embedding_input_sha256 == 'abc'
