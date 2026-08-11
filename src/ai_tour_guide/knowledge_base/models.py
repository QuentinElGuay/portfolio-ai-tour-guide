"""SQLAlchemy ORM mappings for the knowledge-base tables.

The database schema remains defined in :mod:`ai_tour_guide.database.tables`.
These classes map ORM behavior and relationships onto those existing
``Table`` objects so constraints, indexes, and column definitions have a
single source of truth.
"""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import DeclarativeBase, Mapped, relationship

from ai_tour_guide.domain.chunks import EmbeddedChunk
from ai_tour_guide.domain.documents import DocumentRecord
from ai_tour_guide.ingestion.artifacts import ChunkingMetadata
from ai_tour_guide.knowledge_base.tables import (
    document_chunks,
    documents,
    embedding_models,
)
from ai_tour_guide.knowledge_base.tables import (
    metadata as table_metadata,
)


class Base(DeclarativeBase):
    """Declarative base sharing the Core schema metadata."""

    metadata = table_metadata


class EmbeddingModelRow(Base):
    """Stored configuration and provenance for an embedding model."""

    __table__ = embedding_models

    embedding_model_id: Mapped[int]
    provider: Mapped[str]
    model_name: Mapped[str]
    model_revision: Mapped[str]
    dimensions: Mapped[int]
    normalized: Mapped[bool]
    tokenizer_name: Mapped[str | None]
    tokenizer_revision: Mapped[str | None]
    max_input_tokens: Mapped[int | None]
    distance_metric: Mapped[str]
    created_at: Mapped[datetime]

    documents: Mapped[list[DocumentRow]] = relationship(
        back_populates='embedding_model',
    )

    def __repr__(self) -> str:
        return (
            'EmbeddingModelRow('
            f'embedding_model_id={self.embedding_model_id!r}, '
            f'provider={self.provider!r}, '
            f'model_name={self.model_name!r}, '
            f'model_revision={self.model_revision!r}'
            ')'
        )


class DocumentRow(Base):
    """Persisted source document and its ingestion provenance."""

    __table__ = documents

    document_id: Mapped[int]
    embedding_model_id: Mapped[int]
    collection: Mapped[str | None]
    version: Mapped[str | None]
    title: Mapped[str]
    source_url: Mapped[str]
    publisher: Mapped[str | None]
    publication_date: Mapped[date | None]
    authors: Mapped[list[str]]
    subject: Mapped[str | None]
    keywords: Mapped[list[str]]
    language: Mapped[str | None]
    creator: Mapped[str | None]
    producer: Mapped[str | None]
    format: Mapped[str | None]
    creation_date: Mapped[datetime | None]
    modification_date: Mapped[datetime | None]
    source_page_count: Mapped[int | None]
    page_count: Mapped[int | None]
    source_checksum: Mapped[str | None]
    parser_version: Mapped[str | None]
    chunking_version: Mapped[str | None]
    target_chunk_chars: Mapped[int | None]
    max_chunk_chars: Mapped[int | None]
    target_chunk_tokens: Mapped[int | None]
    max_chunk_tokens: Mapped[int | None]
    chunk_overlap_tokens: Mapped[int | None]
    embedded_at: Mapped[datetime | None]
    created_at: Mapped[datetime]

    embedding_model: Mapped[EmbeddingModelRow] = relationship(
        back_populates='documents',
    )
    chunks: Mapped[list[DocumentChunkRow]] = relationship(
        back_populates='document',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='DocumentChunkRow.chunk_index',
    )

    def __repr__(self) -> str:
        return (
            'DocumentRow('
            f'document_id={self.document_id!r}, '
            f'collection={self.collection!r}, '
            f'version={self.version!r}, '
            f'title={self.title!r}, '
            f'source_url={self.source_url!r}'
            ')'
        )


class DocumentChunkRow(Base):
    """Persisted retrieval chunk and its dense embedding."""

    __table__ = document_chunks

    document_id: Mapped[int]
    chunk_id: Mapped[str]
    chunk_index: Mapped[int]
    section_path: Mapped[list[str]]
    text: Mapped[str]
    embedding_text: Mapped[str]
    page_start: Mapped[int | None]
    page_end: Mapped[int | None]
    character_count: Mapped[int]
    token_count: Mapped[int | None]
    content_hash: Mapped[str | None]
    embedding_input_sha256: Mapped[str | None]
    embedding: Mapped[list[float] | None]
    search_vector: Mapped[Any]
    created_at: Mapped[datetime]

    document: Mapped[DocumentRow] = relationship(
        back_populates='chunks',
    )

    def __repr__(self) -> str:
        return (
            'DocumentChunkRow('
            f'document_id={self.document_id!r}, '
            f'chunk_id={self.chunk_id!r}, '
            f'chunk_index={self.chunk_index!r}'
            ')'
        )


class ModelFactory:
    """Create transient ORM rows from ingestion domain objects.

    The factory unwraps nested domain values and converts immutable tuples to
    mutable lists suitable for PostgreSQL array and vector columns.
    """

    @staticmethod
    def create_document(
        document: DocumentRecord,
        *,
        embedding_model_id: int,
        chunking: ChunkingMetadata,
        chunks: Sequence[EmbeddedChunk] = (),
    ) -> DocumentRow:
        """Create a document row with child chunk rows ready for a session.

        Primary keys and timestamps are omitted so PostgreSQL can generate
        them. Adding the returned row to a session also persists its chunks
        through the configured ``save-update`` relationship cascade.
        """
        metadata = document.metadata

        row = DocumentRow(
            embedding_model_id=embedding_model_id,
            collection=document.collection,
            version=document.version,
            title=metadata.title,
            source_url=metadata.source_url,
            publisher=metadata.publisher,
            publication_date=metadata.publication_date,
            authors=list(metadata.authors),
            subject=metadata.subject,
            keywords=list(metadata.keywords),
            creator=metadata.creator,
            producer=metadata.producer,
            format=metadata.format,
            creation_date=metadata.creation_date,
            modification_date=metadata.modification_date,
            source_page_count=metadata.source_page_count,
            page_count=metadata.page_count,
            source_checksum=document.source_checksum,
            target_chunk_chars=chunking.target_chars,
            max_chunk_chars=chunking.max_chars,
        )
        row.chunks = [ModelFactory.create_chunk(chunk) for chunk in chunks]
        return row

    @staticmethod
    def create_chunk(chunk: EmbeddedChunk) -> DocumentChunkRow:
        """Create a chunk row to attach to a :class:`DocumentRow`."""
        source = chunk.chunk

        return DocumentChunkRow(
            chunk_id=source.chunk_id,
            chunk_index=source.chunk_index,
            section_path=list(source.section_path),
            text=source.text,
            embedding_text=source.embedding_text,
            page_start=source.page_start,
            page_end=source.page_end,
            character_count=source.character_count,
            embedding_input_sha256=chunk.embedding_input_sha256,
            embedding=list(chunk.embedding),
        )


__all__ = [
    'Base',
    'DocumentChunkRow',
    'DocumentRow',
    'EmbeddingModelRow',
    'ModelFactory',
]
