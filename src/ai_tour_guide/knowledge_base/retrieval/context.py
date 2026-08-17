"""Production retrieval orchestration: raw search followed by LLM-context expansion."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_tour_guide.knowledge_base.database.connection import create_database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.search.models import (
    HybridSearchSettings,
    SearchMode,
    SearchResult,
)
from ai_tour_guide.knowledge_base.search.strategies import create_search_strategy

from .models import RetrievedContext

ContextIdentity = tuple[int, str]


def retrieve_section_chunks(
    session: Session,
    *,
    document: DocumentRow,
    section_id: str,
) -> tuple[DocumentChunkRow, ...]:
    """Load one document's sibling chunks for a section in stable reading order."""
    statement = (
        select(DocumentChunkRow)
        .where(DocumentChunkRow.document_id == document.document_id)
        .where(DocumentChunkRow.section_id == section_id)
        .order_by(
            DocumentChunkRow.section_chunk_index.asc(),
            DocumentChunkRow.chunk_index.asc(),
        )
    )
    return tuple(session.scalars(statement).all())


def build_retrieved_contexts(
    session: Session,
    results: Iterable[SearchResult],
) -> tuple[RetrievedContext, ...]:
    """Deduplicate search hits by document section before expanding siblings."""
    grouped: dict[ContextIdentity, list[SearchResult]] = {}

    for result in results:
        identity = (
            result.chunk.document_id,
            result.chunk.section_id,
        )
        grouped.setdefault(identity, []).append(result)

    contexts: list[RetrievedContext] = []

    # A dict preserves the order in which each unique identity is first seen.
    for search_results in grouped.values():
        first_result = search_results[0]
        document = first_result.document
        section_id = first_result.chunk.section_id

        siblings = retrieve_section_chunks(
            session,
            document=document,
            section_id=section_id,
        )

        contexts.append(
            RetrievedContext(
                document=document,
                section_id=section_id,
                context_chunks=siblings,
                # Keep the original objects: rank, score and score kind are untouched.
                search_results=tuple(search_results),
            )
        )

    return tuple(contexts)


def retrieve_context(
    query: str,
    *,
    search_mode: SearchMode = SearchMode.VECTOR,
    k: int = 5,
    hybrid_settings: HybridSearchSettings | None = None,
) -> tuple[RetrievedContext, ...]:
    """Search for relevant chunks and expand their sections into temporary LLM contexts."""
    engine = create_database_engine()

    strategy = create_search_strategy(search_mode, hybrid_settings=hybrid_settings)

    try:
        with Session(engine) as session:
            results = strategy.search(
                session,
                query,
                k=k,
            )
            return build_retrieved_contexts(session, results)
    finally:
        engine.dispose()


__all__ = ['build_retrieved_contexts', 'retrieve_context', 'retrieve_section_chunks']
