"""SQLAlchemy ORM mappings for the knowledge-base tables.

The database schema remains defined in :mod:`ai_tour_guide.database.tables`.
These classes map ORM behavior and relationships onto those existing
``Table`` objects so constraints, indexes, and column definitions have a
single source of truth.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import DeclarativeBase, Mapped, relationship

from ai_tour_guide.database.tables import (
    document_chunks,
    documents,
    embedding_models,
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
    tokenizer_name: Mapped[str | None]
    tokenizer_revision: Mapped[str | None]
    max_input_tokens: Mapped[int | None]
    distance_metric: Mapped[str]
    created_at: Mapped[datetime]

    documents: Mapped[list['DocumentRow']] = relationship(
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
    embedding_model_id: Mapped[int | None]
    collection: Mapped[str]
    version: Mapped[str | None]
    title: Mapped[str]
    pdf_url: Mapped[str]
    publisher: Mapped[str | None]
    publication_date: Mapped[date | None]
    authors: Mapped[list[str]]
    subject: Mapped[str | None]
    keywords: Mapped[list[str]]
    language: Mapped[str | None]
    creator: Mapped[str | None]
    producer: Mapped[str | None]
    pdf_format: Mapped[str | None]
    pdf_creation_date: Mapped[str | None]
    pdf_modification_date: Mapped[str | None]
    source_page_count: Mapped[int | None]
    parsed_page_count: Mapped[int | None]
    source_hash: Mapped[str | None]
    parser_version: Mapped[str | None]
    chunking_version: Mapped[str | None]
    target_chunk_chars: Mapped[int | None]
    max_chunk_chars: Mapped[int | None]
    target_chunk_tokens: Mapped[int | None]
    max_chunk_tokens: Mapped[int | None]
    chunk_overlap_tokens: Mapped[int | None]
    embedded_at: Mapped[datetime | None]
    created_at: Mapped[datetime]

    embedding_model: Mapped['EmbeddingModelRow | None'] = relationship(
        back_populates='documents',
    )
    chunks: Mapped[list['DocumentChunkRow']] = relationship(
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
            f'pdf_url={self.pdf_url!r}'
            ')'
        )


class DocumentChunkRow(Base):
    """Persisted retrieval chunk and its dense embedding."""

    __table__ = document_chunks

    chunk_id: Mapped[int]
    document_id: Mapped[int]
    chunk_key: Mapped[str]
    chunk_index: Mapped[int]
    section_path: Mapped[list[str]]
    text: Mapped[str]
    embedding_text: Mapped[str]
    page_start: Mapped[int | None]
    page_end: Mapped[int | None]
    character_count: Mapped[int]
    token_count: Mapped[int | None]
    content_hash: Mapped[str | None]
    embedding_input_hash: Mapped[str | None]
    embedding: Mapped[list[float] | None]
    search_vector: Mapped[Any]
    created_at: Mapped[datetime]

    document: Mapped[DocumentRow] = relationship(
        back_populates='chunks',
    )

    def __repr__(self) -> str:
        return (
            'DocumentChunkRow('
            f'chunk_id={self.chunk_id!r}, '
            f'document_id={self.document_id!r}, '
            f'chunk_key={self.chunk_key!r}, '
            f'chunk_index={self.chunk_index!r}'
            ')'
        )


__all__ = [
    'Base',
    'DocumentChunkRow',
    'DocumentRow',
    'EmbeddingModelRow',
]