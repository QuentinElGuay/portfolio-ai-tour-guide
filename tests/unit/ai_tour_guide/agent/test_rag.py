import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from ai_tour_guide.agent.rag.models import (
    CitationValidationResult,
    GeneratedAnswer,
    SourceReference,
)
from ai_tour_guide.agent.rag.pipeline import answer_question, answer_question_async
from ai_tour_guide.agent.responses import INSUFFICIENT_CONTEXT_ANSWER
from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.retrieval.context import build_retrieved_contexts
from ai_tour_guide.knowledge_base.search.models import (
    ScoreKind,
    SearchMetadata,
    SearchResult,
)


def _document() -> DocumentRow:
    return DocumentRow(
        document_id=1,
        title='Guide',
        source_url='https://example.test/guide',
    )


def _chunk(
    document: DocumentRow, *, chunk_id: str, index: int, page: int
) -> DocumentChunkRow:
    return DocumentChunkRow(
        document_id=document.document_id,
        chunk_id=chunk_id,
        chunk_index=index,
        section_id='coast',
        section_chunk_index=index,
        section_path=['Guide', 'Coast'],
        text=chunk_id,
        embedding_text=chunk_id,
        page_start=page,
        page_end=page,
        character_count=len(chunk_id),
        document=document,
    )


def _search_result(chunk: DocumentChunkRow, *, rank: int) -> SearchResult:
    return SearchResult(
        chunk=chunk,
        search=SearchMetadata(
            rank=rank,
            score=0.9,
            score_kind=ScoreKind.COSINE_SIMILARITY,
        ),
    )


@patch('ai_tour_guide.agent.rag.pipeline.validate_citations')
@patch('ai_tour_guide.agent.rag.pipeline.build_messages')
@patch('ai_tour_guide.agent.rag.pipeline.retrieve_context')
def test_answer_question_retrieves_context_and_returns_sources(
    retrieve_context: MagicMock,
    build_messages: MagicMock,
    validate_citations: MagicMock,
) -> None:
    """Verify that answering a question retrieves context, sends it to the LLM, and preserves its sources."""
    context = MagicMock()
    retrieve_context.return_value = (context,)
    build_messages.return_value = ({'role': 'user', 'content': 'Question'},)
    source = SourceReference(
        'https://example.test/guide', None, 'Guide', None, None, None, (3,)
    )
    validate_citations.return_value = CitationValidationResult((source,), ())
    client = MagicMock()
    client.answer_question = AsyncMock(return_value=GeneratedAnswer('Answer.'))

    result = asyncio.run(answer_question_async('Question', client=client))

    retrieve_context.assert_called_once()
    assert retrieve_context.call_args.kwargs['search_mode'].value == 'hybrid'
    build_messages.assert_called_once_with('Question', (context,))
    client.answer_question.assert_awaited_once_with(build_messages.return_value)
    assert result.answer == 'Answer.'
    assert isinstance(result.request_id, UUID)
    assert result.contexts == (context,)
    assert result.sources == (source,)


@patch('ai_tour_guide.agent.rag.pipeline.answer_question_async', new_callable=AsyncMock)
def test_answer_question_assigns_and_propagates_request_id(
    answer_question_async_mock: AsyncMock,
) -> None:
    expected = MagicMock()
    answer_question_async_mock.return_value = expected

    result = answer_question('Question')

    request_id = answer_question_async_mock.call_args.kwargs['request_id']
    assert isinstance(request_id, UUID)
    assert result is expected


@patch('ai_tour_guide.agent.rag.pipeline.retrieve_context', return_value=())
def test_answer_question_handles_empty_retrieval(retrieve_context: MagicMock) -> None:
    """Verify that an unanswered retrieval returns the insufficient-context response without sources."""
    client = MagicMock()
    client.answer_question = AsyncMock()

    result = asyncio.run(answer_question_async('Question', client=client))

    assert result.answer == INSUFFICIENT_CONTEXT_ANSWER
    assert result.contexts == ()
    assert result.sources == ()
    client.answer_question.assert_not_awaited()
    retrieve_context.assert_called_once()


@patch('ai_tour_guide.agent.rag.pipeline.create_default_llm_client', return_value=None)
def test_answer_question_requires_llm_configuration(
    create_default_llm_client: MagicMock,
) -> None:
    """Verify that question answering fails gracefully when no LLM client is configured."""
    with pytest.raises(RuntimeError, match='No LLM client is configured'):
        asyncio.run(answer_question_async('Question'))

    create_default_llm_client.assert_called_once_with()


def test_build_context_preserves_source_identity_and_pages() -> None:
    """Verify that LLM context preserves the identity, page, rank, and score of the retrieved source chunk."""
    document = _document()
    chunk = _chunk(document, chunk_id='chunk-1', index=0, page=3)
    result = _search_result(chunk, rank=1)
    session = MagicMock()
    with patch(
        'ai_tour_guide.knowledge_base.retrieval.context.retrieve_section_chunks',
        return_value=(chunk,),
    ):
        contexts = build_retrieved_contexts(session, (result,))

    context = contexts[0]
    assert context.source_document is document
    assert context.pages == (3,)
    assert context.search_results == (result,)
    assert context.search_results[0].search.rank == 1
    assert context.search_results[0].search.score == 0.9


def test_build_contexts_deduplicates_a_section_and_keeps_all_retrievals() -> None:
    """Verify that chunks from the same section share one context while retaining every retrieval that matched it."""
    document = _document()
    first = _chunk(document, chunk_id='chunk-1', index=0, page=3)
    second = _chunk(document, chunk_id='chunk-2', index=1, page=4)
    results = (_search_result(first, rank=1), _search_result(second, rank=2))
    session = MagicMock()
    with patch(
        'ai_tour_guide.knowledge_base.retrieval.context.retrieve_section_chunks',
        return_value=(first, second),
    ) as retrieve_section_chunks:
        contexts = build_retrieved_contexts(session, results)

    assert len(contexts) == 1
    assert contexts[0].context_chunks == (first, second)
    assert contexts[0].search_results == results
    retrieve_section_chunks.assert_called_once_with(
        session, document=document, section_id='coast'
    )
