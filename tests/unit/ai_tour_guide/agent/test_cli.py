from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ai_tour_guide.agent.cli import main
from ai_tour_guide.knowledge_base.retrieval import (
    RetrievedChunk,
    ScoreKind,
    SourceMetadata,
)


def _chunk(*, page_start: int | None = 2, page_end: int | None = 3):
    return SimpleNamespace(
        chunk_id='brittany:chunk-0001',
        page_start=page_start,
        page_end=page_end,
        text='Visit the Brittany coast.',
    )


def _retrieved_chunk():
    return RetrievedChunk(
        chunk=_chunk(),
        rank=1,
        score=0.98765,
        score_kind=ScoreKind.COSINE_SIMILARITY,
        source=SourceMetadata(
            document_id=7,
            chunk_id='brittany:chunk-0001',
            title='A guide to Brittany',
            source_url='https://example.com/brittany',
            publisher='Tourism Board',
            publication_date=date(2026, 1, 2),
            collection='tour-guides',
            version='2026',
            section_path=('Brittany', 'Coast'),
            page_start=2,
            page_end=3,
        ),
    )


@patch('ai_tour_guide.agent.cli.retrieve')
def test_search_command_prints_chunks(retrieve: MagicMock) -> None:
    retrieve.return_value = [_retrieved_chunk()]

    result = CliRunner().invoke(main, ['search', 'Brittany coast', '--k', '1'])

    assert result.exit_code == 0
    assert (
        result.output == 'brittany:chunk-0001 (pages 2-3) '
        '[rank 1, score 0.9877 cosine_similarity]\n'
        'Visit the Brittany coast.\n'
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
