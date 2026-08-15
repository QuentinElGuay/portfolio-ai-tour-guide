"""Temporary runtime objects representing context actually provided to the LLM."""

from dataclasses import dataclass

from ai_tour_guide.knowledge_base.search.models import SearchResult, SourceDocumentMetadata


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """One deduplicated section of LLM context and the evidence that selected/provides it."""

    section_id: str
    text: str
    search_results: tuple[SearchResult, ...]
    sources: tuple[SourceDocumentMetadata, ...]


__all__ = ['RetrievedContext']
