from types import SimpleNamespace

from ai_tour_guide.agent.rag.models import CitationInvalidReason, LLMCitation
from ai_tour_guide.agent.rag.sources import validate_citations
from ai_tour_guide.knowledge_base.retrieval import (
    RetrievedChunk,
    ScoreKind,
    SourceMetadata,
)


def _item(page: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=SimpleNamespace(text='text'),
        rank=page,
        score=1.0,
        score_kind=ScoreKind.TEXT_RANK,
        source=SourceMetadata(
            document_id=1,
            chunk_id=f'chunk-{page}',
            title='Guide',
            source_url='https://example.com/guide',
            publisher=None,
            publication_date=None,
            collection=None,
            version='2026',
            section_path=(),
            page_start=page,
            page_end=page,
        ),
    )


def test_partial_range_keeps_known_pages_and_retains_original_invalid_claim() -> None:
    result = validate_citations(
        (LLMCitation('https://example.com/guide', '2026', 2, 4),), (_item(2), _item(4))
    )
    assert result.references[0].pages == (2, 4)
    assert result.invalid_citations[0].page_start == 2
    assert result.invalid_citations[0].reason is CitationInvalidReason.UNSUPPORTED_PAGE


def test_unknown_document_is_invalid() -> None:
    result = validate_citations(
        (LLMCitation('https://other.test', None, 1, 1),), (_item(1),)
    )
    assert result.invalid_citations[0].reason is CitationInvalidReason.UNKNOWN_DOCUMENT
