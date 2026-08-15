"""Skeleton tests for production context retrieval orchestration."""


def test_retrieve_searches_then_builds_contexts_in_same_session() -> None:
    """Call ``retrieve(query, mode=..., k=..., hybrid_settings=...)``.

    Required mocks: engine/Session context, ``search_with_session`` returning SearchResults, and
    ``build_retrieved_contexts`` returning RetrievedContexts.
    Expected verification: raw search happens first, context expansion receives the same session and those
    results, and only RetrievedContext objects are returned to the RAG/LLM layer.
    """
    pass


def test_retrieve_disposes_engine_when_search_or_context_expansion_fails() -> None:
    """Call ``retrieve`` while either search or context building raises.

    Required mocks: owned engine, Session context and one failing dependency per parametrized case.
    Expected verification: exception propagates and the engine is always disposed.
    """
    pass
