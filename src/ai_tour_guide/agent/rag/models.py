"""Models returned by the RAG application layer."""

from dataclasses import dataclass

from ai_tour_guide.knowledge_base.models import DocumentChunkRow


@dataclass(frozen=True)
class RAGResult:
    """An answer together with the chunks used as its source material."""

    answer: str
    chunks: list[DocumentChunkRow]


__all__ = ['RAGResult']
