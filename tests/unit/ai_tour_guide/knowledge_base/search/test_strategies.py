"""Skeleton tests for SearchStrategy implementations."""


def test_text_strategy_returns_ranked_search_results_without_embedding() -> None:
    """Call ``TextSearchStrategy.search(session, query, k=k)``.

    Required mocks: ``search_text`` and ``source_metadata_from_chunk``; mocked Session and scored chunks.
    Expected verification: ranks start at one, scores remain text ranks, ScoreKind is TEXT_RANK, and no
    embedding configuration/embedder is involved.
    """
    pass


def test_vector_strategy_embeds_once_and_normalizes_distance() -> None:
    """Call ``VectorSearchStrategy(embedder).search(session, query, k=k)``.

    Required mocks: embedder with metadata/embed_query, ``search_vector``, provenance conversion.
    Expected verification: query is embedded exactly once, metadata is forwarded to vector search, raw
    distance becomes higher-is-better score and score kind matches the configured distance metric.
    """
    pass


def test_hybrid_strategy_composes_vector_text_and_rrf() -> None:
    """Call ``HybridSearchStrategy(vector, text, settings).search``.

    Required mocks: two SearchStrategy implementations returning deterministic SearchResult rankings and
    a patched ``reciprocal_rank_fusion`` if isolating composition.
    Expected verification: both strategies receive the same session/query/k and configured weights/rank
    constant are forwarded to fusion.
    """
    pass


def test_create_search_strategy_constructs_only_required_dependencies() -> None:
    """Call ``create_search_strategy`` for TEXT, VECTOR and HYBRID modes.

    Required mocks: EmbeddingSettings and FastEmbedder for vector-capable modes.
    Expected verification: text mode does not create an embedder; vector injects one into VectorSearchStrategy;
    hybrid composes vector and text strategies with supplied/default HybridSearchSettings.
    """
    pass
