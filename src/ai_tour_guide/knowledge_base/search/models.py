"""Immutable search-domain models shared by strategies, evaluations, and retrieval."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from math import isfinite

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow


class SearchMode(StrEnum):
    """Supported ranking strategies."""

    VECTOR = 'vector'
    TEXT = 'text'
    HYBRID = 'hybrid'


class SearchMode(StrEnum):
    """Supported knowledge-base retrieval strategies."""

    VECTOR = 'vector'
    TEXT = 'text'
    HYBRID = 'hybrid'


class ScoreKind(StrEnum):
    """Meaning of a normalized search score."""

    COSINE_SIMILARITY = 'cosine_similarity'
    L2_RELEVANCE = 'l2_relevance'
    INNER_PRODUCT = 'inner_product'
    TEXT_RANK = 'text_rank'
    RRF = 'rrf'


@dataclass(frozen=True, slots=True)
class SearchMetadata:
    """Ranking metadata produced by one search strategy."""

    rank: int
    score: float
    score_kind: ScoreKind


@dataclass(frozen=True, slots=True)
class SourceDocumentMetadata:
    """Stable provenance of one matched or context-provided chunk."""

    document_id: int
    chunk_id: str
    title: str
    url: str
    publisher: str | None
    publication_date: date | None
    collection: str | None
    version: str | None
    section_id: str
    section_path: tuple[str, ...]
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One raw ranked match returned by a search strategy."""

    chunk: DocumentChunkRow
    search: SearchMetadata
    source: SourceDocumentMetadata


DEFAULT_RRF_RANK_CONSTANT = 60


@dataclass(frozen=True, slots=True)
class HybridSearchSettings:
    """Weights and rank constant used for reciprocal-rank fusion."""

    vector_weight: float = 1.0
    text_weight: float = 1.0
    rank_constant: int = DEFAULT_RRF_RANK_CONSTANT

    def __post_init__(self) -> None:
        if self.vector_weight < 0 or not isfinite(self.vector_weight):
            raise ValueError('vector_weight must be a finite non-negative number')
        if self.text_weight < 0 or not isfinite(self.text_weight):
            raise ValueError('text_weight must be a finite non-negative number')
        if self.vector_weight == 0 and self.text_weight == 0:
            raise ValueError('at least one hybrid search weight must be greater than zero')
        if self.rank_constant < 0:
            raise ValueError('rank_constant must be non-negative')


__all__ = [
    'DEFAULT_RRF_RANK_CONSTANT',
    'HybridSearchSettings',
    'ScoreKind',
    'SearchMetadata',
    'SearchMode',
    'SearchResult',
    'SourceDocumentMetadata',
]
