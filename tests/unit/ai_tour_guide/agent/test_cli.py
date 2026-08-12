import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ai_tour_guide.agent.cli import main
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGResult, SourceReference
from ai_tour_guide.knowledge_base.retrieval import SearchMode


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


@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_prints_normalized_sources(answer_question: MagicMock) -> None:
    answer_question.return_value = _result()
    result = CliRunner().invoke(main, ['ask', 'What?', '--mode', 'text', '--k', '2'])
    assert result.exit_code == 0
    assert json.loads(result.output) == {
        'schema_version': 1,
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


@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_verbose_prints_full_rag_result(answer_question: MagicMock) -> None:
    answer_question.return_value = _result()
    result = CliRunner().invoke(main, ['ask', 'What?', '--verbose'])
    assert result.exit_code == 0
    assert json.loads(result.output)['schema_version'] == 1
