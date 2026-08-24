"""Tests for Core table definitions."""

from ai_tour_guide.knowledge_base.database.tables import (
    document_chunks,
    documents,
    embedding_models,
    llm_model_pricing,
    metadata,
)


def test_tables_share_one_metadata_registry() -> None:
    """Verify that all persistence tables use the exported Core metadata."""
    assert {
        embedding_models.metadata,
        documents.metadata,
        document_chunks.metadata,
        llm_model_pricing.metadata,
    } == {metadata}


def test_llm_model_pricing_stores_directional_token_costs() -> None:
    """Pricing keeps input and output rates distinct for accurate estimates."""
    assert {
        'provider',
        'model',
        'input_cost_per_token',
        'cached_input_cost_per_token',
        'output_cost_per_token',
        'currency',
        'effective_from',
    } <= set(llm_model_pricing.c.keys())
    constraints = {constraint.name for constraint in llm_model_pricing.constraints}
    assert 'uq_llm_model_pricing_version' in constraints


def test_document_chunks_contains_section_and_search_columns() -> None:
    """Verify that chunks retain sibling, provenance, vector, and text-search data."""
    assert {
        'section_id',
        'section_chunk_index',
        'section_path',
        'embedding',
        'embedding_input_sha256',
        'search_vector',
    } <= set(document_chunks.c.keys())
    constraints = {constraint.name for constraint in document_chunks.constraints}
    assert 'ck_document_chunks_page_range' in constraints
    assert 'ck_document_chunks_embedding_input_sha256_required' in constraints


def test_vector_indexes_cover_all_supported_distance_metrics() -> None:
    """Verify that HNSW indexes support cosine, L2, and inner-product queries."""
    vector_indexes = {
        index.name: index.dialect_options['postgresql'].get('ops')
        for index in document_chunks.indexes
        if index.name and 'embedding_' in index.name
    }
    assert vector_indexes == {
        'ix_document_chunks_embedding_cosine_hnsw': {'embedding': 'vector_cosine_ops'},
        'ix_document_chunks_embedding_l2_hnsw': {'embedding': 'vector_l2_ops'},
        'ix_document_chunks_embedding_inner_product_hnsw': {
            'embedding': 'vector_ip_ops'
        },
    }
