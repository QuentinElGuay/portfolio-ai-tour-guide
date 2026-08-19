import json
from unittest.mock import MagicMock, patch
from uuid import UUID

from click.testing import CliRunner

from ai_tour_guide.agent.cli import main
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGResult, SourceReference
from ai_tour_guide.knowledge_base.search import DEFAULT_SEARCH_MODE, SearchMode


def _result() -> RAGResult:
    return RAGResult(
        question='What?',
        mode=SearchMode.TEXT,
        k=2,
        messages=(),
        generated=GeneratedAnswer('The coast is beautiful.'),
        sources=(
            SourceReference(
                'https://example.com/guide', '2026', 'Guide', None, None, None, (4, 12)
            ),
        ),
    )


@patch('ai_tour_guide.agent.cli.retrieve_context')
def test_search_command_prints_chunks(retrieve_context: MagicMock) -> None:
    """Verify that the search command displays retrieved chunks and their retrieval metadata."""
    result = MagicMock()
    result.chunk.chunk_id = 'chunk-1'
    result.chunk.text = 'The coast is beautiful.'
    result.page_start = 4
    result.page_end = 5
    result.search.rank = 1
    result.search.score = 0.9876
    result.search.score_kind.value = 'cosine_similarity'
    context = MagicMock(search_results=(result,))
    retrieve_context.return_value = (context,)

    invocation = CliRunner().invoke(main, ['search', 'coast'])

    assert invocation.exit_code == 0
    assert invocation.output == (
        'chunk-1 (pages 4-5) [rank 1, score 0.9876 cosine_similarity]\n'
        'The coast is beautiful.\n'
    )
    retrieve_context.assert_called_once_with(
        'coast', search_mode=DEFAULT_SEARCH_MODE, k=5
    )


@patch('ai_tour_guide.agent.cli.store_rag_result')
@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_prints_answer_and_compact_sources(
    answer_question: MagicMock, store_rag_result: MagicMock
) -> None:
    """Verify that the ask command displays the answer followed by compact source references."""
    answer_question.return_value = _result()

    invocation = CliRunner().invoke(main, ['ask', 'What?'])

    assert invocation.exit_code == 0
    assert json.loads(invocation.output) == {
        'schema_version': 1,
        'request_id': str(answer_question.return_value.request_id),
        'answer': 'The coast is beautiful.',
        'sources': [
            {
                'source_url': 'https://example.com/guide',
                'version': '2026',
                'title': 'Guide',
                'publisher': None,
                'collection': None,
                'publication_date': None,
                'pages': [4, 12],
            }
        ],
    }
    answer_question.assert_called_once_with('What?', mode=DEFAULT_SEARCH_MODE, k=5)
    store_rag_result.assert_called_once_with(
        answer_question.return_value.request_id, answer_question.return_value.to_dict()
    )


@patch('ai_tour_guide.agent.cli.store_feedback', return_value=True)
def test_feedback_command_stores_helpful_feedback(store_feedback: MagicMock) -> None:
    request_id = UUID('11111111-1111-1111-1111-111111111111')

    invocation = CliRunner().invoke(
        main,
        [
            'feedback',
            str(request_id),
            '--helpful',
            '--comment',
            'Clear answer.',
        ],
    )

    assert invocation.exit_code == 0
    assert f'Feedback stored for request {request_id}.' in invocation.output
    store_feedback.assert_called_once_with(request_id, True, 'Clear answer.')


@patch('ai_tour_guide.agent.cli.store_feedback', return_value=False)
def test_feedback_command_rejects_unknown_request(store_feedback: MagicMock) -> None:
    request_id = UUID('22222222-2222-2222-2222-222222222222')

    invocation = CliRunner().invoke(
        main, ['feedback', str(request_id), '--not-helpful']
    )

    assert invocation.exit_code != 0
    assert 'Unknown RAG result request ID.' in invocation.output
    store_feedback.assert_called_once_with(request_id, False, None)


@patch('ai_tour_guide.agent.cli.store_feedback')
@patch('ai_tour_guide.agent.cli.store_rag_result')
@patch('ai_tour_guide.agent.cli.answer_question')
def test_chat_command_stores_answer_and_positive_feedback(
    answer_question: MagicMock,
    store_rag_result: MagicMock,
    store_feedback: MagicMock,
) -> None:
    answer_question.return_value = _result()

    invocation = CliRunner().invoke(
        main,
        ['chat'],
        input='What?\npositive\n/exit\n',
    )

    assert invocation.exit_code == 0
    assert 'Guide: The coast is beautiful.' in invocation.output
    store_rag_result.assert_called_once_with(
        answer_question.return_value.request_id,
        answer_question.return_value.to_dict(),
    )
    store_feedback.assert_called_once_with(
        answer_question.return_value.request_id, True
    )


@patch('ai_tour_guide.agent.cli.store_feedback')
@patch('ai_tour_guide.agent.cli.store_rag_result')
@patch('ai_tour_guide.agent.cli.answer_question')
def test_chat_command_can_skip_feedback(
    answer_question: MagicMock,
    store_rag_result: MagicMock,
    store_feedback: MagicMock,
) -> None:
    answer_question.return_value = _result()

    invocation = CliRunner().invoke(
        main,
        ['chat'],
        input='What?\nskip\n/exit\n',
    )

    assert invocation.exit_code == 0
    store_rag_result.assert_called_once()
    store_feedback.assert_not_called()


@patch('ai_tour_guide.agent.cli.store_rag_result')
@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_deduplicates_source_references(
    answer_question: MagicMock, store_rag_result: MagicMock
) -> None:
    """Verify that the ask command does not display duplicate references to the same source pages."""
    answer_question.return_value = RAGResult(
        question='What?',
        mode=SearchMode.HYBRID,
        k=2,
        messages=(),
        generated=GeneratedAnswer('Answer.'),
        sources=(
            SourceReference(
                'https://example.com/guide', '2026', 'Guide', None, None, None, (4,)
            ),
            SourceReference(
                'https://example.com/guide', '2026', 'Guide', None, None, None, (12,)
            ),
        ),
    )

    invocation = CliRunner().invoke(main, ['ask', 'What?'])

    assert invocation.exit_code == 0
    sources = json.loads(invocation.output)['sources']
    assert len(sources) == 1
    assert sources[0]['pages'] == [4, 12]


@patch('ai_tour_guide.agent.cli.store_rag_result')
@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_orders_pages(
    answer_question: MagicMock, store_rag_result: MagicMock
) -> None:
    """Verify that source page references are displayed in ascending page order."""
    answer_question.return_value = RAGResult(
        question='What?',
        mode=SearchMode.HYBRID,
        k=2,
        messages=(),
        generated=GeneratedAnswer('Answer.'),
        sources=(
            SourceReference(
                'https://example.com/guide', '2026', 'Guide', None, None, None, (12, 4)
            ),
        ),
    )

    invocation = CliRunner().invoke(main, ['ask', 'What?'])

    assert invocation.exit_code == 0
    assert json.loads(invocation.output)['sources'][0]['pages'] == [4, 12]


@patch('ai_tour_guide.agent.cli.store_rag_result')
@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_prints_normalized_sources(
    answer_question: MagicMock, store_rag_result: MagicMock
) -> None:
    answer_question.return_value = _result()

    invocation = CliRunner().invoke(main, ['ask', 'What?'])

    assert invocation.exit_code == 0
    source = json.loads(invocation.output)['sources'][0]
    assert source == {
        'source_url': 'https://example.com/guide',
        'version': '2026',
        'title': 'Guide',
        'publisher': None,
        'collection': None,
        'publication_date': None,
        'pages': [4, 12],
    }


@patch('ai_tour_guide.agent.cli.store_rag_result')
@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_verbose_prints_full_rag_result(
    answer_question: MagicMock, store_rag_result: MagicMock
) -> None:
    answer_question.return_value = _result()
    result = CliRunner().invoke(main, ['ask', 'What?', '--verbose'])
    assert result.exit_code == 0
    assert json.loads(result.output)['schema_version'] == 1
