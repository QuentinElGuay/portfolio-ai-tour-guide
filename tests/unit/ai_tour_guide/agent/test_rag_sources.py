from ai_tour_guide.agent.rag.models import CitationInvalidReason, LLMCitation
from ai_tour_guide.agent.rag.sources import validate_citations
from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search.models import (
    ScoreKind,
    SearchMetadata,
    SearchResult,
)


def _context(*pages: int) -> RetrievedContext:
    document = DocumentRow(
        document_id=1,
        title='Guide',
        source_url='https://example.com/guide',
        version='2026',
    )
    chunks = tuple(
        DocumentChunkRow(
            document_id=document.document_id,
            chunk_id=f'chunk-{page}',
            chunk_index=index,
            section_id='section-a',
            section_chunk_index=index,
            section_path=['Guide', 'section-a'],
            text='text',
            embedding_text='text',
            page_start=page,
            page_end=page,
            character_count=4,
            document=document,
        )
        for index, page in enumerate(pages)
    )
    return RetrievedContext(
        document=document,
        section_id='section-a',
        context_chunks=chunks,
        search_results=tuple(
            SearchResult(
                chunk=chunk,
                search=SearchMetadata(
                    rank=index + 1,
                    score=1.0,
                    score_kind=ScoreKind.TEXT_RANK,
                ),
            )
            for index, chunk in enumerate(chunks)
        ),
    )


def test_partial_range_keeps_known_pages_and_retains_original_invalid_claim() -> None:
    result = validate_citations(
        (LLMCitation('https://example.com/guide', '2026', 2, 4),),
        (_context(2, 4),),
    )
    assert result.references[0].pages == (2, 4)
    assert result.invalid_citations[0].page_start == 2
    assert result.invalid_citations[0].reason is CitationInvalidReason.UNSUPPORTED_PAGE


def test_unknown_document_is_invalid() -> None:
    result = validate_citations(
        (LLMCitation('https://other.test', None, 1, 1),),
        (_context(1),),
    )
    assert result.invalid_citations[0].reason is CitationInvalidReason.UNKNOWN_DOCUMENT
