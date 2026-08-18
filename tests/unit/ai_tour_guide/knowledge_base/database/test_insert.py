"""Skeleton tests for transactional inserts."""


def test_get_or_create_embedding_model_returns_compatible_existing_row() -> None:
    """Call ``get_or_create_embedding_model(session, metadata)`` when ``session.scalar`` finds a row.

    Required fixtures/mocks: mocked Session, EmbeddingMetadata, compatible EmbeddingModelRow.
    Expected verification: existing row is returned and no new row is added/flushed.
    """


def test_get_or_create_embedding_model_rejects_incompatible_existing_row() -> None:
    """Call ``get_or_create_embedding_model`` with stored dimensions/normalization/distance differing.

    Required fixtures: mocked session, embedding metadata and conflicting stored row.
    Expected verification: ``EmbeddingModelConfigurationError`` is raised.
    """


def test_insert_document_rejects_duplicate_source_identity() -> None:
    """Call ``insert_document`` when the source_url/version query reports an existing document ID.

    Required fixtures: mocked Session, DocumentRecord, non-empty EmbeddedChunk sequence, ChunkingConfig.
    Expected verification: ``DocumentAlreadyExistsError`` is raised and ModelFactory is not called.
    """


def test_insert_document_with_chunks_is_atomic_and_disposes_engine() -> None:
    """Call ``insert_document_with_chunks`` with valid domain/embedding/chunking fixtures.

    Required mocks: engine, Session context/transaction, get-or-create and insert helpers.
    Expected verification: both writes share one transaction, returned document_id is propagated, and the
    engine is disposed even when persistence raises.
    """
