import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ai_tour_guide.agent.cli import main
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGResult, SourceReference
from ai_tour_guide.knowledge_base.search import SearchMode


def _result() -> RAGResult:
    return RAGResult(
        question='What?',
        mode=SearchMode.TEXT,
        k=2,
        context='',
        messages=(),
        generated=GeneratedAnswer('The coast is beautiful.'),
        sources=(
            SourceReference(
                'https://example.com/guide', '2026', 'Guide', None, None, None, (4, 12)
            ),
        ),
    )


@patch('ai_tour_guide.agent.cli.retrieve')
def test_search_command_prints_chunks(retrieve: MagicMock) -> None:
    """Verify that the search command displays retrieved chunks and their retrieval metadata."""
    assert False


@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_prints_answer_and_compact_sources(
    answer_question: MagicMock,
) -> None:
    """Verify that the ask command displays the answer followed by compact source references."""


@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_deduplicates_source_references(
    answer_question: MagicMock,
) -> None:
    """Verify that the ask command does not display duplicate references to the same source pages."""
    assert False


@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_orders_pages(
    answer_question: MagicMock,
) -> None:
    """Verify that source page references are displayed in ascending page order."""
    assert False


@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_prints_normalized_sources(answer_question: MagicMock) -> None:

    assert False


@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_verbose_prints_full_rag_result(answer_question: MagicMock) -> None:
    answer_question.return_value = _result()
    result = CliRunner().invoke(main, ['ask', 'What?', '--verbose'])
    assert result.exit_code == 0
    assert json.loads(result.output)['schema_version'] == 1
