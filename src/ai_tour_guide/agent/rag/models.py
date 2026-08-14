"""Models returned by the RAG application layer."""

from dataclasses import dataclass, field

from ai_tour_guide.knowledge_base.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.retrieval import RetrievedChunk


@dataclass(frozen=True, slots=True)
class Context:
    """One deduplicated section of LLM context and its retrieval evidence."""

    section_id: str | None
    text: str
    chunks: tuple[RetrievedChunk, ...]


@dataclass(frozen=True)
class RAGResult:
    """An answer together with the chunks used as its source material."""

    answer: str
    contexts: tuple[Context, ...] = field(default_factory=tuple)

    @property
    def chunks(self) -> list[DocumentChunkRow]:
        """Return the retrieved chunks without their ranking metadata."""
        return [chunk for context in self.contexts for chunk in context.chunks]


__all__ = ['Context', 'RAGResult']
