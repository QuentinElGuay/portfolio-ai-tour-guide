"""Public orchestration for raw ranked search results."""

from sqlalchemy.orm import Session

from ai_tour_guide.knowledge_base.database.connection import create_database_engine

from .models import DEFAULT_SEARCH_MODE, HybridSearchSettings, SearchMode, SearchResult
from .strategies import create_search_strategy


def search_with_session(
    session: Session,
    query: str,
    *,
    mode: SearchMode = DEFAULT_SEARCH_MODE,
    k: int = 5,
    hybrid_settings: HybridSearchSettings | None = None,
) -> list[SearchResult]:
    """Execute one search inside an existing database session."""
    selected_mode = SearchMode(mode)
    strategy = create_search_strategy(selected_mode, hybrid_settings=hybrid_settings)
    return strategy.search(session, query, k=k)


def search(
    query: str,
    *,
    mode: SearchMode = DEFAULT_SEARCH_MODE,
    k: int = 5,
    hybrid_settings: HybridSearchSettings | None = None,
) -> list[SearchResult]:
    """Return raw ranked matches for production callers and search evaluation."""
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            return search_with_session(
                session,
                query,
                mode=mode,
                k=k,
                hybrid_settings=hybrid_settings,
            )
    finally:
        engine.dispose()


__all__ = ['search', 'search_with_session']
