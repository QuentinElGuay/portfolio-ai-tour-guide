"""Skeleton tests for raw search orchestration."""


def test_search_with_session_selects_strategy_and_returns_raw_results() -> None:
    """Call ``search_with_session(session, query, mode=..., k=..., hybrid_settings=...)``.

    Required mocks: ``create_search_strategy`` returning a mocked SearchStrategy and a Session fixture.
    Expected verification: mode is normalized, strategy receives the caller session/query/k, and SearchResult
    objects are returned unchanged for retrieval evaluation.
    """
    pass


def test_search_owns_session_and_engine_lifecycle() -> None:
    """Call public ``search(query, ...)``.

    Required mocks: ``create_database_engine``, SQLAlchemy ``Session`` context, and ``search_with_session``.
    Expected verification: one session is opened, raw results are returned, and the engine is disposed both
    on success and on search failure.
    """
    pass
