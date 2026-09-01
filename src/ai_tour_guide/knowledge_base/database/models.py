"""SQLAlchemy ORM mappings over the Core schema declared in ``tables.py``."""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import DeclarativeBase, Mapped, relationship

from ai_tour_guide.domain.chunks import EmbeddedChunk
from ai_tour_guide.domain.documents import DocumentRecord
from ai_tour_guide.ingestion.config import ChunkingConfig

from .tables.public import document_chunks, documents, embedding_models
from .tables.public import metadata as table_metadata


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
        back_populates='embedding_model'
    )


class DocumentRow(Base):
    """Persisted source document and its ingestion provenance."""

    __table__ = documents

    document_id: Mapped[int]
    embedding_model_id: Mapped[int]
    collection: Mapped[str | None]
    version: Mapped[str | None]
    title: Mapped[str]
    destination: Mapped[str]
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
    section_chunk_min_depth: Mapped[int | None]
    section_chunk_max_depth: Mapped[int | None]
    target_chunk_tokens: Mapped[int | None]
    max_chunk_tokens: Mapped[int | None]
    chunk_overlap_tokens: Mapped[int | None]
    embedded_at: Mapped[datetime | None]
    created_at: Mapped[datetime]

    embedding_model: Mapped[EmbeddingModelRow] = relationship(
        back_populates='documents'
    )
    chunks: Mapped[list[DocumentChunkRow]] = relationship(
        back_populates='document',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='DocumentChunkRow.chunk_index',
    )


class DocumentChunkRow(Base):
    """Persisted retrieval chunk and its dense embedding."""

    __table__ = document_chunks

    document_id: Mapped[int]
    chunk_id: Mapped[str]
    chunk_index: Mapped[int]
    section_id: Mapped[str]
    section_chunk_index: Mapped[int | None]
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

    document: Mapped[DocumentRow] = relationship(back_populates='chunks')


class ModelFactory:
    """Create transient ORM rows from ingestion domain objects."""

    @staticmethod
    def create_document(
        document: DocumentRecord,
        *,
        embedding_model_id: int,
        chunking: ChunkingConfig,
        chunks: Sequence[EmbeddedChunk] = (),
    ) -> DocumentRow:
        """Create a document aggregate ready to be added to a SQLAlchemy session."""
        metadata = document.metadata
        row = DocumentRow(
            embedding_model_id=embedding_model_id,
            collection=document.collection,
            version=document.version,
            title=metadata.title,
            destination=document.destination,
            source_url=metadata.source_url,
            publisher=metadata.publisher,
            publication_date=metadata.publication_date,
            authors=list(metadata.authors),
            subject=metadata.subject,
            keywords=list(metadata.keywords),
            language=getattr(metadata, 'language', None),
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
            section_chunk_min_depth=chunking.section_chunk_min_depth,
            section_chunk_max_depth=chunking.section_chunk_max_depth,
            target_chunk_tokens=getattr(chunking, 'target_tokens', None),
            max_chunk_tokens=getattr(chunking, 'max_tokens', None),
            chunk_overlap_tokens=getattr(chunking, 'overlap_tokens', None),
        )
        row.chunks = [ModelFactory.create_chunk(chunk) for chunk in chunks]
        return row

    @staticmethod
    def create_chunk(chunk: EmbeddedChunk) -> DocumentChunkRow:
        """Create a persisted chunk row from one embedded ingestion chunk."""
        source = chunk.chunk
        return DocumentChunkRow(
            chunk_id=source.chunk_id,
            chunk_index=source.chunk_index,
            section_id=source.section_id,
            section_chunk_index=source.section_chunk_index,
            section_path=list(source.section_path),
            text=source.text,
            embedding_text=source.embedding_text,
            page_start=source.page_start,
            page_end=source.page_end,
            character_count=source.character_count,
            token_count=getattr(source, 'token_count', None),
            content_hash=getattr(source, 'content_hash', None),
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
