"""Reusable retrieval orchestration for the knowledge base."""

from collections.abc import Iterable
from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_tour_guide.knowledge_base.connection import create_database_engine
from ai_tour_guide.knowledge_base.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.retrieval_models import (
    HybridSearchSettings,
    RetrievedChunk,
    SearchMode,
    SiblingChunks,
)
from ai_tour_guide.knowledge_base.retrieval_strategies import _create_search_strategy


def retrieve_siblings(
    session: Session,
    chunk: DocumentChunkRow,
) -> SiblingChunks:
    """Return a chunk's document-scoped section siblings in reading order."""
    section_id = chunk.section_id
    statement = (
        select(DocumentChunkRow)
        .where(DocumentChunkRow.document_id == chunk.document_id)
        .where(DocumentChunkRow.section_id == section_id)
        .order_by(
            DocumentChunkRow.section_chunk_index.asc(),
            DocumentChunkRow.chunk_index.asc(),
        )
    )
    return SiblingChunks(
        section_id=section_id,
        chunks=tuple(session.scalars(statement).all()),
    )


def _retrieve_sibling_sections(
    session: Session,
    ranked_chunks: Iterable[RetrievedChunk],
) -> list[RetrievedChunk]:
    """Expand ranked chunks into one deduplicated result per document section."""
    sections: list[RetrievedChunk] = []
    seen: set[tuple[int, str]] = set()

    for result in ranked_chunks:
        siblings = retrieve_siblings(session, result.chunk)
        identity = (result.source.document_id, siblings.section_id)
        if identity in seen:
            continue
        seen.add(identity)
        sections.append(
            replace(
                result,
                section_id=siblings.section_id,
                text=siblings.text,
            )
        )

    return sections


def retrieve(
    query: str,
    *,
    mode: SearchMode = SearchMode.VECTOR,
    k: int = 5,
    hybrid_settings: HybridSearchSettings | None = None,
    retrieve_siblings: bool = True,
) -> list[RetrievedChunk]:
    selected_mode = SearchMode(mode)

    strategy = _create_search_strategy(
        selected_mode,
        hybrid_settings=hybrid_settings,
    )

    engine = create_database_engine()

    try:
        with Session(engine) as session:
            results = strategy.search(
                session,
                query,
                k=k,
            )

            if retrieve_siblings:
                return _retrieve_sibling_sections(
                    session,
                    results,
                )

            return results
    finally:
        engine.dispose()


__all__ = [
    'SearchMode',
    'retrieve',
    'retrieve_siblings',
]
