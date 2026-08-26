"""Transactional persistence operations for the knowledge base."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_tour_guide.domain.chunks import EmbeddedChunk
from ai_tour_guide.domain.documents import DocumentRecord
from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.ingestion.config import ChunkingConfig

from .connection import create_database_engine
from .models import DocumentRow, EmbeddingModelRow, ModelFactory


class DocumentAlreadyExistsError(RuntimeError):
    """Raised when insertion would replace an existing document."""


class EmbeddingModelConfigurationError(RuntimeError):
    """Raised when stored and effective embedding configurations disagree."""


def get_or_create_embedding_model(
    session: Session,
    metadata: EmbeddingMetadata,
) -> EmbeddingModelRow:
    """Return the stored embedding-model row for ``metadata``, inserting it when absent."""
    if metadata.dimensions <= 0:
        raise ValueError('embedding dimensions must be greater than zero')

    statement = select(EmbeddingModelRow).where(
        EmbeddingModelRow.provider == metadata.provider,
        EmbeddingModelRow.model_name == metadata.model_name,
        EmbeddingModelRow.model_revision == metadata.model_revision,
    )
    existing = session.scalar(statement)
    if existing is None:
        session.execute(
            postgres_insert(EmbeddingModelRow.__table__)
            .values(
                provider=metadata.provider,
                model_name=metadata.model_name,
                model_revision=metadata.model_revision,
                dimensions=metadata.dimensions,
                normalized=metadata.normalized,
                tokenizer_name=getattr(metadata, 'tokenizer_name', None),
                tokenizer_revision=getattr(metadata, 'tokenizer_revision', None),
                max_input_tokens=getattr(metadata, 'max_input_tokens', None),
                distance_metric=metadata.distance_metric,
            )
            .on_conflict_do_nothing(constraint='uq_embedding_models_identity')
        )
        existing = session.scalar(statement)

    if existing is None:
        raise RuntimeError('Embedding model insert did not produce a database row.')
    if (
        existing.dimensions != metadata.dimensions
        or existing.normalized != metadata.normalized
        or existing.distance_metric != metadata.distance_metric
    ):
        raise EmbeddingModelConfigurationError(
            'Stored embedding model configuration does not match the effective ingestion model'
        )
    return existing


def insert_document(
    session: Session,
    document: DocumentRecord,
    chunks: Sequence[EmbeddedChunk],
    chunking: ChunkingConfig,
    *,
    embedding_model_id: int,
    replace_existing: bool = False,
) -> DocumentRow:
    """Insert one document aggregate into an existing transaction."""
    if not chunks:
        raise ValueError('a document must contain at least one embedded chunk')

    existing = session.scalar(
        select(DocumentRow.document_id).where(
            DocumentRow.source_url == document.metadata.source_url,
            DocumentRow.version == document.version,
        )
    )
    if existing is not None and not replace_existing:
        raise DocumentAlreadyExistsError(
            'Document already exists for source identity '
            f'({document.metadata.source_url!r}, {document.version!r})'
        )
    if existing is not None:
        session.delete(existing)
        session.flush()

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
    return (
        getattr(diagnostic, 'constraint_name', None)
        == 'uq_documents_source_url_version'
    )


def insert_document_with_chunks(
    document: DocumentRecord,
    chunks: Sequence[EmbeddedChunk],
    chunking_metadata: ChunkingConfig,
    embedding_metadata: EmbeddingMetadata,
    *,
    replace_existing: bool = False,
) -> int:
    """Persist a fully embedded document atomically and return its database ID."""
    engine = create_database_engine()
    try:
        with Session(engine, expire_on_commit=False) as session:
            try:
                with session.begin():
                    embedding_model = get_or_create_embedding_model(
                        session, embedding_metadata
                    )
                    row = insert_document(
                        session,
                        document,
                        chunks,
                        chunking_metadata,
                        embedding_model_id=embedding_model.embedding_model_id,
                        replace_existing=replace_existing,
                    )
            except IntegrityError as exc:
                if _is_document_identity_violation(exc):
                    raise DocumentAlreadyExistsError(
                        'Document was inserted concurrently for source identity '
                        f'({document.metadata.source_url!r}, {document.version!r})'
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
