"""Skeleton tests for Core table definitions."""


def test_tables_share_one_metadata_registry() -> None:
    """Inspect ``embedding_models``, ``documents`` and ``document_chunks`` from ``database.tables``.

    Required inputs: none beyond importing the module with a deterministic embedding dimension setting.
    Expected verification: all tables belong to the exported ``metadata`` object.
    """


def test_document_chunks_contains_section_and_search_columns() -> None:
    """Inspect ``document_chunks.c`` without connecting to PostgreSQL.

    Required inputs: imported Core table.
    Expected verification: section_id, section_chunk_index, section_path, embedding and computed
    search_vector columns exist with the constraints/indexes required by sibling, vector and text search.
    """


def test_vector_indexes_cover_all_supported_distance_metrics() -> None:
    """Inspect indexes declared on ``document_chunks``.

    Required inputs: imported table metadata only.
    Expected verification: HNSW indexes exist for cosine, L2 and inner-product operator classes.
    """
