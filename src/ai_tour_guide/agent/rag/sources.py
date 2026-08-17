"""Citation validation shared by RAG, interfaces, and future evaluation."""

import logging
from collections import OrderedDict
from collections.abc import Sequence

from ai_tour_guide.agent.rag.models import (
    CitationInvalidReason,
    CitationValidationResult,
    InvalidCitation,
    LLMCitation,
    SourceReference,
)
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search.models import SourceMetadata

logger = logging.getLogger(__name__)


def _reference(source: SourceMetadata, pages: Sequence[int] = ()) -> SourceReference:
    return SourceReference(
        source_url=source.url,
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
    source: SourceMetadata | None = None,
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
    documents: OrderedDict[tuple[str, str | None], list[SourceMetadata]] = OrderedDict()
    for sources in retrieved.sources:
        documents.setdefault((sources.source.source_url, sources.source.version), []).append(
            sources.source
        )

    valid: OrderedDict[tuple[str, str | None], tuple[SourceMetadata, set[int]]] = (
        OrderedDict()
    )
    invalid: list[InvalidCitation] = []
    for citation in citations:
        document_sources = documents.get((citation.source_url, citation.version))
        if not document_sources:
            invalid.append(_invalid(citation, CitationInvalidReason.UNKNOWN_DOCUMENT))
            continue
        source = document_sources[0]
        start, end = citation.page_start, citation.page_end
        if start is None and end is None:
            if all(
                item.page_start is None and item.page_end is None
                for item in document_sources
            ):
                valid.setdefault(
                    (citation.source_url, citation.version), (source, set())
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
        for sources in document_sources:
            if sources.page_start is None:
                continue
            item_end = sources.page_start if sources.page_end is None else sources.page_end
            supported.update(range(sources.page_start, item_end + 1))
        cited_pages = set(range(start, end + 1))
        confirmed = cited_pages & supported
        if confirmed:
            existing = valid.setdefault(
                (citation.source_url, citation.version), (source, set())
            )
            existing[1].update(confirmed)
        if confirmed != cited_pages:
            invalid.append(
                _invalid(citation, CitationInvalidReason.UNSUPPORTED_PAGE, source)
            )

    return CitationValidationResult(
        references=tuple(_reference(source, pages) for source, pages in valid.values()),
        invalid_citations=tuple(invalid),
    )


__all__ = ['validate_citations']
