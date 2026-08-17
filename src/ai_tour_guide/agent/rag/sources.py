"""Citation validation shared by RAG, interfaces, and future evaluation."""

import logging
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass

from ai_tour_guide.agent.rag.models import (
    CitationInvalidReason,
    CitationValidationResult,
    InvalidCitation,
    LLMCitation,
    SourceReference,
)
from ai_tour_guide.knowledge_base.database.models import DocumentRow
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CitationEvidence:
    """A document and the pages confirmed for a citation."""

    document: DocumentRow
    pages: set[int]


@dataclass(frozen=True, slots=True)
class DocumentIdentity:
    """Stable identity of a versioned source document."""

    source_url: str
    version: str | None


def _reference(source: DocumentRow, pages: Sequence[int] = ()) -> SourceReference:
    return SourceReference(
        source_url=source.source_url,
        version=source.version,
        title=source.title,
        publisher=source.publisher,
        collection=source.collection,
        publication_date=source.publication_date,
        pages=tuple(sorted(set(pages))),
    )


def _invalid(
    citation: LLMCitation,
    reason: CitationInvalidReason,
    source: DocumentRow | None = None,
) -> InvalidCitation:
    if reason is CitationInvalidReason.UNKNOWN_REASON:
        logger.error('Unknown citation validation reason for %r', citation)
    return InvalidCitation(
        source_url=citation.source_url,
        version=citation.version,
        page_start=citation.page_start,
        page_end=citation.page_end,
        reason=reason,
        title=source.title if source else None,
        publisher=source.publisher if source else None,
        collection=source.collection if source else None,
        publication_date=source.publication_date if source else None,
    )


def validate_citations(
    citations: Sequence[LLMCitation], retrieved: Sequence[RetrievedContext]
) -> CitationValidationResult:
    """Trust only page evidence actually supplied by the knowledge base."""
    documents: OrderedDict[DocumentIdentity, list[RetrievedContext]] = OrderedDict()
    for context in retrieved:
        document = context.source_document
        documents.setdefault(
            DocumentIdentity(document.source_url, document.version), []
        ).append(context)

    valid: OrderedDict[DocumentIdentity, CitationEvidence] = OrderedDict()
    invalid: list[InvalidCitation] = []
    for citation in citations:
        identity = DocumentIdentity(citation.source_url, citation.version)
        document_sources = documents.get(identity)
        if not document_sources:
            invalid.append(_invalid(citation, CitationInvalidReason.UNKNOWN_DOCUMENT))
            continue
        source = document_sources[0].source_document
        start, end = citation.page_start, citation.page_end
        if start is None and end is None:
            if all(not context.pages for context in document_sources):
                valid.setdefault(
                    identity,
                    CitationEvidence(source, set()),
                )
            else:
                invalid.append(
                    _invalid(citation, CitationInvalidReason.UNSUPPORTED_PAGE, source)
                )
            continue
        if (
            start is None
            or not isinstance(start, int)
            or start <= 0
            or (end is not None and (not isinstance(end, int) or end < start))
        ):
            invalid.append(
                _invalid(citation, CitationInvalidReason.MALFORMED_RANGE, source)
            )
            continue
        end = start if end is None else end
        supported: set[int] = set()
        for context in document_sources:
            supported.update(context.pages)
        cited_pages = set(range(start, end + 1))
        confirmed = cited_pages & supported
        if confirmed:
            existing = valid.setdefault(
                identity,
                CitationEvidence(source, set()),
            )
            existing.pages.update(confirmed)
        if confirmed != cited_pages:
            invalid.append(
                _invalid(citation, CitationInvalidReason.UNSUPPORTED_PAGE, source)
            )

    return CitationValidationResult(
        references=tuple(
            _reference(evidence.document, tuple(evidence.pages))
            for evidence in valid.values()
        ),
        invalid_citations=tuple(invalid),
    )


__all__ = ['validate_citations']
