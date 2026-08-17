from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from math import isfinite

from ai_tour_guide.knowledge_base.models import DocumentChunkRow


class SearchMode(StrEnum):
    """Supported knowledge-base retrieval strategies."""

    VECTOR = 'vector'
    TEXT = 'text'
    HYBRID = 'hybrid'


class ScoreKind(StrEnum):
    """Meaning of a retrieval score."""

    COSINE_SIMILARITY = 'cosine_similarity'
    L2_RELEVANCE = 'l2_relevance'
    INNER_PRODUCT = 'inner_product'
    TEXT_RANK = 'text_rank'
    RRF = 'rrf'


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Stable provenance needed to identify and cite a retrieved chunk."""

    document_id: int
    chunk_id: str
    title: str
    source_url: str
    publisher: str | None
    publication_date: date | None
    collection: str | None
    version: str | None
    section_path: tuple[str, ...]
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A ranked chunk and the score that produced its position."""

    chunk: DocumentChunkRow
    rank: int
    score: float
    score_kind: ScoreKind
    source: SourceMetadata
    section_id: str | None = None
    text: str | None = None

    def __post_init__(self) -> None:
        """Default section metadata to the matched chunk when not expanded."""
        if self.section_id is None:
            object.__setattr__(
                self,
                'section_id',
                getattr(self.chunk, 'section_id', None),
            )
        if self.text is None:
            object.__setattr__(self, 'text', self.chunk.text)


@dataclass(frozen=True, slots=True)
class SiblingChunks:
    """All chunks belonging to one document section in reading order."""

    section_id: str
    chunks: tuple[DocumentChunkRow, ...]

    @property
    def text(self) -> str:
        """Return sibling text in ascending section-local order."""
        return '\n\n'.join(chunk.text for chunk in self.chunks)


DEFAULT_RRF_RANK_CONSTANT = 60


@dataclass(frozen=True, slots=True)
class HybridSearchSettings:
    """Configuration for combining vector and full-text rankings."""

    vector_weight: float = 1.0
    text_weight: float = 1.0
    rank_constant: int = DEFAULT_RRF_RANK_CONSTANT

    def __post_init__(self) -> None:
        if self.vector_weight < 0 or not isfinite(self.vector_weight):
            raise ValueError('vector_weight must be a finite non-negative number')
        if self.text_weight < 0 or not isfinite(self.text_weight):
            raise ValueError('text_weight must be a finite non-negative number')
        if self.vector_weight == 0 and self.text_weight == 0:
            raise ValueError(
                'at least one hybrid search weight must be greater than zero'
            )
        if self.rank_constant < 0:
            raise ValueError('rank_constant must be non-negative')


__all__ = [
    'DEFAULT_RRF_RANK_CONSTANT',
    'HybridSearchSettings',
    'RetrievedChunk',
    'ScoreKind',
    'SiblingChunks',
    'SourceMetadata',
]
