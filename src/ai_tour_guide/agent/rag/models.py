"""Immutable RAG contracts and JSON-safe serialization."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Any

from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.knowledge_base.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.retrieval import RetrievedChunk, SearchMode

RAG_RESULT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Context:
    """One deduplicated section of LLM context and its retrieval evidence."""

    section_id: str | None
    text: str
    chunks: tuple[RetrievedChunk, ...]
   

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
    llm_metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    raw_provider_response: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'citations', tuple(self.citations))
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
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _serialize_retrieved(result: RetrievedChunk) -> dict[str, Any]:
    source = result.source
    chunk = result.chunk
    return {
        'rank': result.rank,
        'score': result.score,
        'score_kind': result.score_kind.value,
        'document_id': source.document_id,
        'chunk_id': source.chunk_id,
        'source_url': source.source_url,
        'version': source.version,
        'title': source.title,
        'publisher': source.publisher,
        'collection': source.collection,
        'publication_date': _json_value(source.publication_date),
        'section_path': list(source.section_path),
        'page_start': source.page_start,
        'page_end': source.page_end,
        'content_hash': getattr(chunk, 'content_hash', None),
        'text': chunk.text,
    }


@dataclass(frozen=True, slots=True)
class RAGResult:
    question: str
    mode: SearchMode
    k: int
    context: str  #TODO: check the use after merge
    messages: tuple[Message, ...]
    generated: GeneratedAnswer
    retrieved: tuple[RetrievedChunk, ...] = ()
    sources: tuple[SourceReference, ...] = ()
    invalid_citations: tuple[InvalidCitation, ...] = ()
    error: RAGError | None = None
    retrieval_latency_ms: float | None = None
    generation_latency_ms: float | None = None
    total_latency_ms: float | None = None
    retrieval_metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    llm_metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    raw_provider_response: Any = None
    contexts: tuple[Context, ...] = field(default_factory=tuple)

    @property
    def chunks(self) -> list[DocumentChunkRow]:
        """Return the retrieved chunks without their ranking metadata."""
        return [chunk for context in self.contexts for chunk in context.chunks]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, 'messages', tuple(dict(message) for message in self.messages)
        )
        object.__setattr__(self, 'retrieved', tuple(self.retrieved))
        object.__setattr__(self, 'sources', tuple(self.sources))
        object.__setattr__(self, 'invalid_citations', tuple(self.invalid_citations))
        object.__setattr__(
            self, 'retrieval_metadata', _freeze_mapping(self.retrieval_metadata)
        )
        object.__setattr__(self, 'llm_metadata', _freeze_mapping(self.llm_metadata))

    @property
    def answer(self) -> str:
        return self.generated.answer

    def to_dict(self) -> dict[str, Any]:
        return {
            'schema_version': RAG_RESULT_SCHEMA_VERSION,
            'question': self.question,
            'mode': self.mode.value,
            'k': self.k,
            'context': self.context,
            'messages': _json_value(self.messages),
            'generated': {
                'answer': self.generated.answer,
                'citations': _json_value(self.generated.citations),
            },
            'retrieved': [_serialize_retrieved(item) for item in self.retrieved],
            'sources': [source.to_dict() for source in self.sources],
            'invalid_citations': _json_value(self.invalid_citations),
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
    'Context',
    'GeneratedAnswer',
    'InvalidCitation',
    'LLMCitation',
    'RAGError',
    'RAGResult',
    'SourceReference',
]
