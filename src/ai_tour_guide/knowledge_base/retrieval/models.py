"""Temporary runtime objects representing context actually provided to the LLM."""

from dataclasses import dataclass

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.search.models import SearchResult


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """One unique document section expanded from one or more search hits."""

    source_document: DocumentRow
    section_id: str
    section_path: tuple[str, ...]
    context_chunks: tuple[DocumentChunkRow, ...]
    search_results: tuple[SearchResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, 'context_chunks', tuple(self.context_chunks))
        object.__setattr__(self, 'search_results', tuple(self.search_results))

        if not self.context_chunks:
            raise ValueError('RetrievedContext must contain at least one sibling chunk')
        if not self.search_results:
            raise ValueError('RetrievedContext must contain at least one search result')

        identity = (self.source_document.document_id, self.section_id)

        for chunk in self.context_chunks:
            if (chunk.document_id, chunk.section_id) != identity:
                raise ValueError(
                    'all context chunks must belong to the context document and section'
                )

        for result in self.search_results:
            if (result.chunk.document_id, result.chunk.section_id) != identity:
                raise ValueError(
                    'all search results must belong to the context document and section'
                )

        expected_path = self.section_path
        if any(
            tuple(chunk.section_path) != expected_path for chunk in self.context_chunks
        ):
            raise ValueError(
                'all context chunks must share the RetrievedContext section path'
            )

    @property
    def text(self) -> str:
        """Join sibling chunks in the order returned by the sibling query."""
        return '\n\n'.join(chunk.text for chunk in self.context_chunks)

    @property
    def pages(self) -> tuple[int, ...]:
        """Return sorted, deduplicated pages with unavailable pages omitted."""
        page_ranges = (
            range(chunk.page_start, (chunk.page_end or chunk.page_start) + 1)
            for chunk in self.context_chunks
            if chunk.page_start is not None
        )
        return tuple(
            sorted({page for page_range in page_ranges for page in page_range})
        )


__all__ = ['RetrievedContext']
