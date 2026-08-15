"""Expand ranked matches into section-level context for the LLM."""

from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.search.models import SearchResult
from ai_tour_guide.knowledge_base.search.provenance import source_metadata_from_chunk

from .models import RetrievedContext


def retrieve_section_chunks(
    session: Session,
    *,
    document_id: int,
    section_id: str,
) -> tuple[DocumentChunkRow, ...]:
    """Load all chunks from one document section in stable reading order."""
    statement = (
        select(DocumentChunkRow)
        .options(selectinload(DocumentChunkRow.document))
        .where(DocumentChunkRow.document_id == document_id)
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
) -> list[RetrievedContext]:
    """Group search hits by document section and expand each group to all sibling chunks."""
    grouped: dict[tuple[int, str], list[SearchResult]] = defaultdict(list)
    order: list[tuple[int, str]] = []

    for result in results:
        identity = (result.source.document_id, result.source.section_id)
        if identity not in grouped:
            order.append(identity)
        grouped[identity].append(result)

    contexts: list[RetrievedContext] = []
    for document_id, section_id in order:
        siblings = retrieve_section_chunks(
            session,
            document_id=document_id,
            section_id=section_id,
        )
        contexts.append(
            RetrievedContext(
                section_id=section_id,
                text='\n\n'.join(chunk.text for chunk in siblings),
                search_results=tuple(grouped[(document_id, section_id)]),
                sources=tuple(source_metadata_from_chunk(chunk) for chunk in siblings),
            )
        )
    return contexts


__all__ = ['build_retrieved_contexts', 'retrieve_section_chunks']
