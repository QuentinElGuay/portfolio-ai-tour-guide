"""Models returned by the RAG application layer."""

from dataclasses import dataclass

from ai_tour_guide.knowledge_base.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.retrieval import RetrievedChunk


@dataclass(frozen=True)
class RAGResult:
    """An answer together with the chunks used as its source material."""

    answer: str
    retrieved: list[RetrievedChunk]

    @property
    def chunks(self) -> list[DocumentChunkRow]:
        """Return the retrieved chunks without their ranking metadata."""
        return [result.chunk for result in self.retrieved]


__all__ = ['RAGResult']
