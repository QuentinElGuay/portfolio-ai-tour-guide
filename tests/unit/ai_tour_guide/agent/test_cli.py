from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ai_tour_guide.agent.cli import main


def _chunk(*, page_start: int | None = 2, page_end: int | None = 3):
    return SimpleNamespace(
        chunk_id='brittany:chunk-0001',
        page_start=page_start,
        page_end=page_end,
        text='Visit the Brittany coast.',
    )


@patch('ai_tour_guide.agent.cli.retrieve')
def test_search_command_prints_chunks(retrieve: MagicMock) -> None:
    retrieve.return_value = [_chunk()]

    result = CliRunner().invoke(main, ['search', 'Brittany coast', '--k', '1'])

    assert result.exit_code == 0
    assert (
        result.output == 'brittany:chunk-0001 (pages 2-3)\nVisit the Brittany coast.\n'
    )
    retrieve.assert_called_once_with('Brittany coast', mode='vector', k=1)


@patch('ai_tour_guide.agent.cli.answer_question')
def test_ask_command_prints_answer_and_compact_sources(
    answer_question: MagicMock,
) -> None:
    answer_question.return_value = SimpleNamespace(
        answer='The coast is beautiful.',
        chunks=[_chunk()],
    )

    result = CliRunner().invoke(
        main,
        ['ask', 'What is worth seeing?', '--mode', 'text', '--k', '2'],
    )

    assert result.exit_code == 0
    assert result.output == (
        'The coast is beautiful.\n\nSources:\n- brittany:chunk-0001 (pages 2-3)\n'
    )
    answer_question.assert_called_once_with('What is worth seeing?', mode='text', k=2)
