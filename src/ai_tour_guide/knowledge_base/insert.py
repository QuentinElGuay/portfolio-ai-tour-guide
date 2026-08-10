"""Transactional persistence operations for the knowledge base."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_tour_guide.knowledge_base.connection import create_database_engine
from ai_tour_guide.knowledge_base.models import (
    DocumentRow,
    EmbeddingModelRow,
    ModelFactory,
)
from ai_tour_guide.domain.chunks import EmbeddedChunk
from ai_tour_guide.domain.documents import DocumentRecord
from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.ingestion.artifacts import ChunkingMetadata


class DocumentAlreadyExistsError(RuntimeError):
    """Raised when insertion would replace an existing document."""


class EmbeddingModelConfigurationError(RuntimeError):
    """Raised when stored and effective embedding configurations disagree."""


def get_or_create_embedding_model(
    session: Session,
    metadata: EmbeddingMetadata,
) -> EmbeddingModelRow:
    """Return an immutable embedding-model record, inserting it if absent."""
    if metadata.dimensions <= 0:
        raise ValueError('embedding dimensions must be greater than zero')

    statement = select(EmbeddingModelRow).where(
        EmbeddingModelRow.provider == metadata.provider,
        EmbeddingModelRow.model_name == metadata.model_name,
        EmbeddingModelRow.model_revision == metadata.model_revision,
    )
    existing = session.scalar(statement)

    if existing is not None:
        if (
            existing.dimensions != metadata.dimensions
            or existing.normalized != metadata.normalized
            or existing.distance_metric != metadata.distance_metric
        ):
            raise EmbeddingModelConfigurationError(
                'Stored embedding model configuration does not match the '
                'effective ingestion model'
            )
        return existing

    embedding_model = EmbeddingModelRow(
        provider=metadata.provider,
        model_name=metadata.model_name,
        model_revision=metadata.model_revision,
        dimensions=metadata.dimensions,
        normalized=metadata.normalized,
        distance_metric=metadata.distance_metric,
    )
    session.add(embedding_model)
    session.flush()
    return embedding_model


def insert_document(
    session: Session,
    document: DocumentRecord,
    chunks: Sequence[EmbeddedChunk],
    chunking: ChunkingMetadata,
    *,
    embedding_model_id: int,
) -> DocumentRow:
    """Insert a new document aggregate without modifying existing rows."""
    if not chunks:
        raise ValueError('a document must contain at least one embedded chunk')

    existing_document_id = session.scalar(
        select(DocumentRow.document_id).where(
            DocumentRow.source_url == document.metadata.source_url,
        )
    )

    if existing_document_id is not None:
        raise DocumentAlreadyExistsError(
            f'Document already exists for source URL {document.metadata.source_url!r}'
        )

    row = ModelFactory.create_document(
        document,
        embedding_model_id=embedding_model_id,
        chunks=chunks,
        chunking=chunking,
    )
    row.embedded_at = datetime.now(UTC)
    session.add(row)
    session.flush()
    return row


def _is_document_identity_violation(exc: IntegrityError) -> bool:
    diagnostic = getattr(exc.orig, 'diag', None)
    return getattr(diagnostic, 'constraint_name', None) == 'uq_documents_source_url'


def insert_document_with_chunks(
    document: DocumentRecord,
    chunks: Sequence[EmbeddedChunk],
    chunking_metadata: ChunkingMetadata,
    embedding_metadata: EmbeddingMetadata,
) -> int:
    """Persist a fully embedded document atomically and return its ID."""
    engine = create_database_engine()

    try:
        with Session(engine, expire_on_commit=False) as session:
            try:
                with session.begin():
                    embedding_model = get_or_create_embedding_model(
                        session,
                        embedding_metadata,
                    )
                    row = insert_document(
                        session,
                        document,
                        chunks,
                        chunking_metadata,
                        embedding_model_id=embedding_model.embedding_model_id,
                    )
            except IntegrityError as exc:
                if _is_document_identity_violation(exc):
                    raise DocumentAlreadyExistsError(
                        'Document was inserted concurrently for source URL '
                        f'{document.metadata.source_url!r}'
                    ) from exc
                raise

            return row.document_id
    finally:
        engine.dispose()


__all__ = [
    'DocumentAlreadyExistsError',
    'EmbeddingModelConfigurationError',
    'get_or_create_embedding_model',
    'insert_document',
    'insert_document_with_chunks',
]
