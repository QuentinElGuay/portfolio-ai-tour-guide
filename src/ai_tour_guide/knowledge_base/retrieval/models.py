"""Temporary runtime objects representing context actually provided to the LLM."""

from dataclasses import dataclass

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.search.models import SearchResult


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """One unique document section expanded from one or more search hits."""

    document: DocumentRow
    section_id: str
    chunks: tuple[DocumentChunkRow, ...]
    search_results: tuple[SearchResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, 'chunks', tuple(self.chunks))
        object.__setattr__(self, 'search_results', tuple(self.search_results))

        if not self.chunks:
            raise ValueError('RetrievedContext must contain at least one sibling chunk')
        if not self.search_results:
            raise ValueError('RetrievedContext must contain at least one search result')

        identity = (self.document.document_id, self.section_id)

        for chunk in self.chunks:
            if (chunk.document_id, chunk.section_id) != identity:
                raise ValueError(
                    'all context chunks must belong to the context document and section'
                )

        for result in self.search_results:
            if (result.chunk.document_id, result.chunk.section_id) != identity:
                raise ValueError(
                    'all search results must belong to the context document and section'
                )

        expected_path = tuple(self.chunks[0].section_path)
        if any(tuple(chunk.section_path) != expected_path for chunk in self.chunks):
            raise ValueError('all context chunks must share the same section path')

    @property
    def section_path(self) -> tuple[str, ...]:
        """Return the shared hierarchical path of this section."""
        return tuple(self.chunks[0].section_path)

    @property
    def text(self) -> str:
        """Join sibling chunks in the order returned by the sibling query."""
        return '\n\n'.join(chunk.text for chunk in self.chunks)

    @property
    def pages(self) -> tuple[int, ...]:
        """Return exact unique pages represented by the expanded context."""
        pages: set[int] = set()

        for chunk in self.chunks:
            if chunk.page_start is None:
                continue
            page_end = chunk.page_start if chunk.page_end is None else chunk.page_end
            pages.update(range(chunk.page_start, page_end + 1))

        return tuple(sorted(pages))


__all__ = ['RetrievedContext']
