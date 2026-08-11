from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
from click.testing import CliRunner

from ai_tour_guide.agent.cli import _search, main


def _chunk(*, page_start: int | None = 2, page_end: int | None = 3):
    return SimpleNamespace(
        chunk_id='brittany:chunk-0001',
        page_start=page_start,
        page_end=page_end,
        text='Visit the Brittany coast.',
    )


@patch('ai_tour_guide.agent.cli._search')
def test_search_command_prints_chunks(search: MagicMock) -> None:
    search.return_value = [_chunk()]

    result = CliRunner().invoke(main, ['search', 'Brittany coast', '--k', '1'])

    assert result.exit_code == 0
    assert (
        result.output == 'brittany:chunk-0001 (pages 2-3)\nVisit the Brittany coast.\n'
    )
    search.assert_called_once_with('Brittany coast', mode='vector', k=1)


@patch('ai_tour_guide.agent.cli.search_vector')
@patch('ai_tour_guide.agent.cli.FastEmbedder')
@patch('ai_tour_guide.agent.cli.create_database_engine')
@patch('ai_tour_guide.agent.cli.Session')
def test_vector_search_embeds_the_query_before_retrieval(
    session_class: MagicMock,
    create_engine: MagicMock,
    embedder_class: MagicMock,
    vector_search: MagicMock,
) -> None:
    engine = MagicMock()
    create_engine.return_value = engine
    session = MagicMock()
    session_class.return_value.__enter__.return_value = session
    embedder_class.return_value.embed_query.return_value = np.array([0.1, 0.2])
    chunk = _chunk()
    vector_search.return_value = [chunk]

    result = _search('Brittany coast', mode='vector', k=1)

    assert result == [chunk]
    embedder_class.return_value.embed_query.assert_called_once_with('Brittany coast')
    vector_search.assert_called_once_with(
        session,
        [0.1, 0.2],
        1,
        embedding_metadata=embedder_class.return_value.metadata,
    )
    engine.dispose.assert_called_once_with()


@patch('ai_tour_guide.agent.cli.search_text')
@patch('ai_tour_guide.agent.cli.FastEmbedder')
@patch('ai_tour_guide.agent.cli.create_database_engine')
@patch('ai_tour_guide.agent.cli.Session')
def test_text_search_does_not_embed_the_query(
    session_class: MagicMock,
    create_engine: MagicMock,
    embedder_class: MagicMock,
    text_search: MagicMock,
) -> None:
    engine = MagicMock()
    create_engine.return_value = engine
    session = MagicMock()
    session_class.return_value.__enter__.return_value = session
    chunk = _chunk(page_start=None, page_end=None)
    text_search.return_value = [chunk]

    result = _search('Brittany coast', mode='text', k=1)

    assert result == [chunk]
    embedder_class.assert_not_called()
    text_search.assert_called_once_with(session, 'Brittany coast', 1)
    engine.dispose.assert_called_once_with()
