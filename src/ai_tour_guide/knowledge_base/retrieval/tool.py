"""Shared, provider-neutral retrieval tool for tourism knowledge."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.knowledge_base.retrieval.context import retrieve_context
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search import DEFAULT_SEARCH_MODE, SearchMode
from ai_tour_guide.knowledge_base.search.models import ScoreKind, SearchResult
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy


@dataclass(frozen=True, slots=True)
class TourismSearchToolSpec:
    """Provider-neutral description of the approved tourism search tool."""

    name: str
    description: str
    input_schema: dict[str, object]


TOURISM_SEARCH_TOOL = TourismSearchToolSpec(
    name='search_tourism_knowledge_base',
    description='Search indexed regional tourism guides.',
    input_schema={
        'type': 'object',
        'properties': {
            'query': {
                'type': 'string',
                'description': 'A focused query for indexed regional tourism guides.',
            }
        },
        'required': ['query'],
        'additionalProperties': False,
    },
)


class RetrievalStatus(StrEnum):
    """Operational and evidence-quality outcome of a knowledge-base search."""

    SUCCESS = 'success'
    LOW_CONFIDENCE = 'low_confidence'
    EMPTY = 'empty'
    ERROR = 'error'


@dataclass(frozen=True, slots=True)
class TourismSearchQuery:
    """Canonical input for the tourism knowledge-base tool."""

    query: str
    mode: SearchMode = DEFAULT_SEARCH_MODE
    k: int = 5

    def __post_init__(self) -> None:
        normalized = self.query.strip()
        if not normalized:
            raise ValueError('query must not be empty')
        if self.k < 1:
            raise ValueError('k must be at least 1')
        object.__setattr__(self, 'query', normalized)
        object.__setattr__(self, 'mode', SearchMode(self.mode))


@dataclass(frozen=True, slots=True)
class RetrievalQualitySettings:
    """Score-kind-specific thresholds for evidence supplied to an LLM.

    Scores are meaningful only within their respective ranking strategies, so a single
    universal threshold would reject or accept evidence inconsistently.
    """

    minimum_cosine_similarity: float = 0.65
    minimum_l2_relevance: float = -1.0
    minimum_inner_product: float = 0.0
    minimum_text_rank: float = 0.05
    minimum_rrf: float = 0.02

    def __post_init__(self) -> None:
        values = (
            self.minimum_cosine_similarity,
            self.minimum_l2_relevance,
            self.minimum_inner_product,
            self.minimum_text_rank,
            self.minimum_rrf,
        )
        if not all(isfinite(value) for value in values):
            raise ValueError('retrieval quality thresholds must be finite')

    def minimum_score(self, score_kind: ScoreKind) -> float:
        """Return the configured threshold for one score representation."""
        thresholds = {
            ScoreKind.COSINE_SIMILARITY: self.minimum_cosine_similarity,
            ScoreKind.L2_RELEVANCE: self.minimum_l2_relevance,
            ScoreKind.INNER_PRODUCT: self.minimum_inner_product,
            ScoreKind.TEXT_RANK: self.minimum_text_rank,
            ScoreKind.RRF: self.minimum_rrf,
        }
        return thresholds[ScoreKind(score_kind)]


DEFAULT_RETRIEVAL_QUALITY_SETTINGS = RetrievalQualitySettings()


@dataclass(frozen=True, slots=True)
class TourismEvidence:
    """One reconstructed source section with ranking and provenance."""

    text: str
    source_url: str
    title: str
    version: str | None
    publisher: str | None
    collection: str | None
    publication_date: str | None
    pages: tuple[int, ...]
    document_id: int
    section_id: str
    section_path: tuple[str, ...]
    rank: int
    score: float
    score_kind: ScoreKind

    def to_dict(self) -> dict[str, object]:
        """Return API-safe provenance metadata without exposing internals."""
        return {
            'text': self.text,
            'source_url': self.source_url,
            'title': self.title,
            'version': self.version,
            'publisher': self.publisher,
            'collection': self.collection,
            'publication_date': self.publication_date,
            'pages': list(self.pages),
            'document_id': self.document_id,
            'section_id': self.section_id,
            'section_path': list(self.section_path),
            'rank': self.rank,
            'score': self.score,
            'score_kind': self.score_kind.value,
        }


@dataclass(frozen=True, slots=True)
class RetrievalToolError:
    """Safe operational error returned when retrieval cannot complete."""

    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class TourismSearchResult:
    """Typed search outcome preserving both valuable and low-score evidence."""

    status: RetrievalStatus
    query: TourismSearchQuery
    evidence: tuple[TourismEvidence, ...] = ()
    low_confidence_evidence: tuple[TourismEvidence, ...] = ()
    contexts: tuple[RetrievedContext, ...] = ()
    low_confidence_contexts: tuple[RetrievedContext, ...] = ()
    error: RetrievalToolError | None = None

    @property
    def all_evidence(self) -> tuple[TourismEvidence, ...]:
        """Return all reconstructed contexts in their original ranking order."""
        return tuple(
            sorted(
                (*self.evidence, *self.low_confidence_evidence),
                key=lambda evidence: evidence.rank,
            )
        )


def _primary_result(context: RetrievedContext) -> SearchResult:
    """Return the best original hit that caused a context to be reconstructed."""
    return min(context.search_results, key=lambda result: result.search.rank)


def _evidence(context: RetrievedContext) -> TourismEvidence:
    """Convert one logical retrieved context into portable evidence."""
    result = _primary_result(context)
    document = context.source_document
    return TourismEvidence(
        text=context.text,
        source_url=document.source_url,
        title=document.title,
        version=document.version,
        publisher=document.publisher,
        collection=document.collection,
        publication_date=(
            document.publication_date.isoformat()
            if document.publication_date is not None
            else None
        ),
        pages=context.pages,
        document_id=document.document_id,
        section_id=context.section_id,
        section_path=context.section_path,
        rank=result.search.rank,
        score=result.search.score,
        score_kind=result.search.score_kind,
    )


def _is_valuable(evidence: TourismEvidence, settings: RetrievalQualitySettings) -> bool:
    """Return whether an evidence item's score is safe to supply to an LLM."""
    return evidence.score >= settings.minimum_score(evidence.score_kind)


def search_tourism_knowledge_base(
    query: TourismSearchQuery | str,
    *,
    quality_settings: RetrievalQualitySettings = DEFAULT_RETRIEVAL_QUALITY_SETTINGS,
    engine: Engine | None = None,
    strategy: SearchStrategy | None = None,
) -> TourismSearchResult:
    """Search guides, reconstruct contexts, and classify evidence quality."""
    selected_query = (
        query if isinstance(query, TourismSearchQuery) else TourismSearchQuery(query)
    )
    try:
        contexts = retrieve_context(
            selected_query.query,
            search_mode=selected_query.mode,
            k=selected_query.k,
            engine=engine,
            strategy=strategy,
        )
    except (OSError, SQLAlchemyError, RuntimeError) as exc:
        return TourismSearchResult(
            status=RetrievalStatus.ERROR,
            query=selected_query,
            error=RetrievalToolError(type(exc).__name__, str(exc)),
        )

    context_evidence = tuple((context, _evidence(context)) for context in contexts)
    if not context_evidence:
        return TourismSearchResult(
            status=RetrievalStatus.EMPTY,
            query=selected_query,
        )

    valuable_pairs = tuple(
        (context, evidence)
        for context, evidence in context_evidence
        if _is_valuable(evidence, quality_settings)
    )
    low_confidence_pairs = tuple(
        (context, evidence)
        for context, evidence in context_evidence
        if not _is_valuable(evidence, quality_settings)
    )
    return TourismSearchResult(
        status=(
            RetrievalStatus.SUCCESS
            if valuable_pairs
            else RetrievalStatus.LOW_CONFIDENCE
        ),
        query=selected_query,
        evidence=tuple(evidence for _, evidence in valuable_pairs),
        low_confidence_evidence=tuple(evidence for _, evidence in low_confidence_pairs),
        contexts=tuple(context for context, _ in valuable_pairs),
        low_confidence_contexts=tuple(context for context, _ in low_confidence_pairs),
    )


__all__ = [
    'DEFAULT_RETRIEVAL_QUALITY_SETTINGS',
    'TOURISM_SEARCH_TOOL',
    'RetrievalQualitySettings',
    'RetrievalStatus',
    'RetrievalToolError',
    'TourismEvidence',
    'TourismSearchQuery',
    'TourismSearchResult',
    'TourismSearchToolSpec',
    'search_tourism_knowledge_base',
]
