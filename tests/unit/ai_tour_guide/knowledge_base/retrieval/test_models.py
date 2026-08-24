"""Tests for the temporary LLM context contract."""

import pytest

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search.models import (
    ScoreKind,
    SearchMetadata,
    SearchResult,
)


def _document(document_id: int = 1) -> DocumentRow:
    return DocumentRow(
        document_id=document_id,
        title=f'Document {document_id}',
        source_url=f'https://example.test/{document_id}',
    )


def _chunk(
    document: DocumentRow,
    *,
    chunk_id: str,
    section_id: str = 'section-a',
    section_chunk_index: int = 0,
    text: str = 'text',
    page_start: int | None = None,
    page_end: int | None = None,
) -> DocumentChunkRow:
    return DocumentChunkRow(
        document_id=document.document_id,
        chunk_id=chunk_id,
        chunk_index=section_chunk_index,
        section_id=section_id,
        section_chunk_index=section_chunk_index,
        section_path=['Guide', section_id],
        text=text,
        embedding_text=text,
        page_start=page_start,
        page_end=page_end,
        character_count=len(text),
        document=document,
    )


def _search_result(chunk: DocumentChunkRow, *, rank: int) -> SearchResult:
    return SearchResult(
        chunk=chunk,
        search=SearchMetadata(
            rank=rank,
            score=1.0 / rank,
            score_kind=ScoreKind.TEXT_RANK,
        ),
    )


def test_retrieved_context_derives_text_path_and_exact_pages_from_siblings() -> None:
    """Verify that retrieved context derives text path and exact pages from siblings."""
    document = _document()
    first = _chunk(
        document,
        chunk_id='chunk-1',
        section_chunk_index=0,
        text='first',
        page_start=8,
        page_end=9,
    )
    second = _chunk(
        document,
        chunk_id='chunk-2',
        section_chunk_index=1,
        text='second',
        page_start=11,
        page_end=11,
    )

    context = RetrievedContext(
        source_document=document,
        section_id='section-a',
        section_path=('Guide', 'section-a'),
        context_chunks=(first, second),
        search_results=(_search_result(first, rank=1),),
    )

    assert context.section_path == ('Guide', 'section-a')
    assert context.text == 'first\n\nsecond'
    assert context.pages == (8, 9, 11)


def test_retrieved_context_keeps_original_search_result_metadata_unchanged() -> None:
    """Verify that retrieved context keeps original search result metadata unchanged."""
    document = _document()
    first = _chunk(document, chunk_id='chunk-1')
    second = _chunk(document, chunk_id='chunk-2', section_chunk_index=1)
    first_result = _search_result(first, rank=1)
    second_result = SearchResult(
        chunk=second,
        search=SearchMetadata(
            rank=4,
            score=0.123,
            score_kind=ScoreKind.COSINE_SIMILARITY,
        ),
    )

    context = RetrievedContext(
        source_document=document,
        section_id='section-a',
        section_path=('Guide', 'section-a'),
        context_chunks=(first, second),
        search_results=(first_result, second_result),
    )

    assert context.search_results == (first_result, second_result)
    assert context.search_results[0] is first_result
    assert context.search_results[1] is second_result
    assert context.search_results[1].search.rank == 4
    assert context.search_results[1].search.score == 0.123
    assert context.search_results[1].search.score_kind is ScoreKind.COSINE_SIMILARITY


def test_retrieved_context_rejects_mixed_document_chunks() -> None:
    """Verify that retrieved context rejects mixed document chunks."""
    document_a = _document(1)
    document_b = _document(2)
    chunk_a = _chunk(document_a, chunk_id='a')
    chunk_b = _chunk(document_b, chunk_id='b')

    with pytest.raises(ValueError, match='context document and section'):
        RetrievedContext(
            source_document=document_a,
            section_id='section-a',
            section_path=('Guide', 'section-a'),
            context_chunks=(chunk_a, chunk_b),
            search_results=(_search_result(chunk_a, rank=1),),
        )


def test_retrieved_context_rejects_search_result_from_another_section() -> None:
    """Verify that retrieved context rejects search result from another section."""
    document = _document()
    sibling = _chunk(document, chunk_id='a')
    other_section = _chunk(document, chunk_id='b', section_id='section-b')

    with pytest.raises(ValueError, match='search results'):
        RetrievedContext(
            source_document=document,
            section_id='section-a',
            section_path=('Guide', 'section-a'),
            context_chunks=(sibling,),
            search_results=(_search_result(other_section, rank=1),),
        )
