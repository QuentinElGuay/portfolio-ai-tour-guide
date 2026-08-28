"""Immutable RAG contracts and JSON-safe serialization."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from ai_tour_guide.agent.chat.models import Emotion, Message
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search import SearchMode
from ai_tour_guide.knowledge_base.search.models import SearchResult

RAG_RESULT_SCHEMA_VERSION = 1


class CitationInvalidReason(StrEnum):
    UNKNOWN_DOCUMENT = 'unknown_document'
    UNSUPPORTED_PAGE = 'unsupported_page'
    MALFORMED_RANGE = 'malformed_range'
    UNKNOWN_REASON = 'unknown_reason'


@dataclass(frozen=True, slots=True)
class LLMCitation:
    source_url: str
    version: str | None
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    answer: str
    citations: tuple[LLMCitation, ...] = ()
    emotion: Emotion = Emotion.NEUTRAL
    llm_metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    raw_provider_response: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'citations', tuple(self.citations))
        object.__setattr__(self, 'emotion', Emotion(self.emotion))
        object.__setattr__(self, 'llm_metadata', _freeze_mapping(self.llm_metadata))


@dataclass(frozen=True, slots=True)
class SourceReference:
    source_url: str
    version: str | None
    title: str
    publisher: str | None
    collection: str | None
    publication_date: date | None
    pages: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        """Normalize source pages for stable API and CLI output."""
        object.__setattr__(self, 'pages', tuple(sorted(set(self.pages))))

    def to_dict(self) -> dict[str, Any]:
        return {
            'source_url': self.source_url,
            'version': self.version,
            'title': self.title,
            'publisher': self.publisher,
            'collection': self.collection,
            'publication_date': _json_value(self.publication_date),
            'pages': list(self.pages),
        }


def _normalize_sources(
    sources: tuple[SourceReference, ...],
) -> tuple[SourceReference, ...]:
    """Merge repeated versioned documents while preserving their first appearance."""
    normalized: dict[tuple[str, str | None], SourceReference] = {}
    for source in sources:
        identity = (source.source_url, source.version)
        existing = normalized.get(identity)
        if existing is None:
            normalized[identity] = source
            continue
        normalized[identity] = SourceReference(
            source_url=existing.source_url,
            version=existing.version,
            title=existing.title,
            publisher=existing.publisher,
            collection=existing.collection,
            publication_date=existing.publication_date,
            pages=existing.pages + source.pages,
        )
    return tuple(normalized.values())


@dataclass(frozen=True, slots=True)
class InvalidCitation:
    source_url: str
    version: str | None
    page_start: int | None
    page_end: int | None
    reason: CitationInvalidReason
    title: str | None = None
    publisher: str | None = None
    collection: str | None = None
    publication_date: date | None = None


@dataclass(frozen=True, slots=True)
class CitationValidationResult:
    references: tuple[SourceReference, ...]
    invalid_citations: tuple[InvalidCitation, ...]
    matched_section_paths: tuple[tuple[tuple[str, ...], ...], ...] = ()


@dataclass(frozen=True, slots=True)
class RAGError:
    stage: str
    type: str
    message: str


def _freeze_mapping(mapping: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(mapping or {}))


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _serialize_search_result(search_result: SearchResult) -> dict[str, Any]:
    source = search_result.document
    search = search_result.search
    chunk = search_result.chunk

    return {
        'rank': search.rank,
        'score': search.score,
        'score_kind': search.score_kind.value,
        'document_id': source.document_id,
        'chunk_id': chunk.chunk_id,
        'source_url': source.source_url,
        'version': source.version,
        'title': source.title,
        'publisher': source.publisher,
        'collection': source.collection,
        'publication_date': _json_value(source.publication_date),
        'section_id': chunk.section_id,
        'section_path': list(chunk.section_path),
        'page_start': search_result.page_start,
        'page_end': search_result.page_end,
        'content_hash': getattr(chunk, 'content_hash', None),
        'text': chunk.text,
    }


def _serialize_context(context: RetrievedContext) -> dict[str, Any]:
    return {
        'section_id': context.section_id,
        'text': context.text,
        'search_results': [
            _serialize_search_result(result) for result in context.search_results
        ],
        'source': {
            'source_url': context.source_document.source_url,
            'version': context.source_document.version,
            'title': context.source_document.title,
        },
    }


@dataclass(frozen=True, slots=True)
class RAGResult:
    question: str
    mode: SearchMode
    k: int
    messages: tuple[Message, ...]
    generated: GeneratedAnswer
    contexts: tuple[RetrievedContext, ...] = field(default_factory=tuple)
    sources: tuple[SourceReference, ...] = ()
    invalid_citations: tuple[InvalidCitation, ...] = ()
    citation_section_paths: tuple[tuple[tuple[str, ...], ...], ...] = ()
    error: RAGError | None = None
    retrieval_latency_ms: int | None = None
    generation_latency_ms: int | None = None
    total_latency_ms: int | None = None
    request_id: UUID = field(default_factory=uuid4)
    retrieval_metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    llm_metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    raw_provider_response: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, 'messages', tuple(dict(message) for message in self.messages)
        )
        object.__setattr__(self, 'sources', _normalize_sources(tuple(self.sources)))
        object.__setattr__(self, 'invalid_citations', tuple(self.invalid_citations))
        object.__setattr__(
            self,
            'citation_section_paths',
            tuple(
                tuple(path for path in paths) for paths in self.citation_section_paths
            ),
        )
        object.__setattr__(
            self, 'retrieval_metadata', _freeze_mapping(self.retrieval_metadata)
        )
        object.__setattr__(self, 'llm_metadata', _freeze_mapping(self.llm_metadata))
        for field_name in (
            'retrieval_latency_ms',
            'generation_latency_ms',
            'total_latency_ms',
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, round(value))

    @property
    def answer(self) -> str:
        return self.generated.answer

    def to_dict(self) -> dict[str, Any]:
        return {
            'schema_version': RAG_RESULT_SCHEMA_VERSION,
            'request_id': str(self.request_id),
            'question': self.question,
            'mode': self.mode.value,
            'k': self.k,
            'messages': _json_value(self.messages),
            'generated': {
                'answer': self.generated.answer,
                'citations': _json_value(self.generated.citations),
                'emotion': self.generated.emotion.value,
            },
            'search_results': [
                _serialize_search_result(result)
                for context in self.contexts
                for result in context.search_results
            ],
            'contexts': [_serialize_context(context) for context in self.contexts],
            'sources': [source.to_dict() for source in self.sources],
            'invalid_citations': _json_value(self.invalid_citations),
            'citation_section_paths': _json_value(self.citation_section_paths),
            'error': _json_value(self.error),
            'retrieval_latency_ms': self.retrieval_latency_ms,
            'generation_latency_ms': self.generation_latency_ms,
            'total_latency_ms': self.total_latency_ms,
            'retrieval_metadata': _json_value(self.retrieval_metadata),
            'llm_metadata': _json_value(self.llm_metadata),
            'raw_provider_response': _json_value(self.raw_provider_response),
        }


__all__ = [
    'RAG_RESULT_SCHEMA_VERSION',
    'CitationInvalidReason',
    'CitationValidationResult',
    'Emotion',
    'GeneratedAnswer',
    'InvalidCitation',
    'LLMCitation',
    'RAGError',
    'RAGResult',
    'SourceReference',
]
