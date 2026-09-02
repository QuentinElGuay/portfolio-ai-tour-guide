"""Provider-neutral typed tools for searching tourism knowledge."""

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.knowledge_base.retrieval.context import retrieve_context
from ai_tour_guide.knowledge_base.search import DEFAULT_SEARCH_MODE, SearchMode
from ai_tour_guide.knowledge_base.search.models import ScoreKind
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
    """Operational outcome of a knowledge-base search."""

    SUCCESS = 'success'
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
class TourismEvidence:
    """A retrieved passage with sufficient provenance for citation validation."""

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


@dataclass(frozen=True, slots=True)
class RetrievalToolError:
    """Safe operational error returned when retrieval cannot complete."""

    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class TourismSearchResult:
    """Typed search outcome distinguishing success, emptiness, and failure."""

    status: RetrievalStatus
    query: TourismSearchQuery
    evidence: tuple[TourismEvidence, ...] = ()
    error: RetrievalToolError | None = None


def search_tourism_knowledge_base(
    query: TourismSearchQuery | str,
    *,
    engine: Engine | None = None,
    strategy: SearchStrategy | None = None,
) -> TourismSearchResult:
    """Search tourism guides and return provider-independent evidence."""
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

    evidence = tuple(
        TourismEvidence(
            text=result.chunk.text,
            source_url=result.document.source_url,
            title=result.document.title,
            version=result.document.version,
            publisher=result.document.publisher,
            collection=result.document.collection,
            publication_date=(
                result.document.publication_date.isoformat()
                if result.document.publication_date is not None
                else None
            ),
            pages=tuple(
                page
                for page in range(
                    result.page_start or 0,
                    (result.page_end or result.page_start or 0) + 1,
                )
                if page > 0
            ),
            document_id=result.document.document_id,
            section_id=result.chunk.section_id,
            section_path=tuple(result.chunk.section_path),
            rank=result.search.rank,
            score=result.search.score,
            score_kind=result.search.score_kind,
        )
        for context in contexts
        for result in context.search_results
    )
    return TourismSearchResult(
        status=RetrievalStatus.SUCCESS if evidence else RetrievalStatus.EMPTY,
        query=selected_query,
        evidence=evidence,
    )


__all__ = [
    'TOURISM_SEARCH_TOOL',
    'RetrievalStatus',
    'RetrievalToolError',
    'TourismEvidence',
    'TourismSearchQuery',
    'TourismSearchResult',
    'TourismSearchToolSpec',
    'search_tourism_knowledge_base',
]
