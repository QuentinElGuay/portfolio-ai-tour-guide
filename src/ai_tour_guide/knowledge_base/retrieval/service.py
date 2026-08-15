"""Production retrieval orchestration: raw search followed by LLM-context expansion."""

from sqlalchemy.orm import Session

from ai_tour_guide.knowledge_base.database.connection import create_database_engine
from ai_tour_guide.knowledge_base.search.models import HybridSearchSettings, SearchMode
from ai_tour_guide.knowledge_base.search.service import search_with_session

from .context import build_retrieved_contexts
from .models import RetrievedContext


def retrieve(
    query: str,
    *,
    mode: SearchMode = SearchMode.VECTOR,
    k: int = 5,
    hybrid_settings: HybridSearchSettings | None = None,
) -> list[RetrievedContext]:
    """Search for relevant chunks and expand their sections into temporary LLM contexts."""
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            results = search_with_session(
                session,
                query,
                mode=mode,
                k=k,
                hybrid_settings=hybrid_settings,
            )
            return build_retrieved_contexts(session, results)
    finally:
        engine.dispose()


__all__ = ['retrieve']
