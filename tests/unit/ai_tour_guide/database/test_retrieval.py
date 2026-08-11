from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sqlalchemy.orm import Session

from ai_tour_guide.knowledge_base.retrieval import (
    DEFAULT_RRF_RANK_CONSTANT,
    HybridSearchSettings,
    SearchMode,
    retrieve,
)


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.model_name = 'test-model'
    settings.normalize = True
    settings.cache_dir = None
    return settings


@patch('ai_tour_guide.knowledge_base.retrieval.search_vector')
@patch('ai_tour_guide.knowledge_base.retrieval.FastEmbedder')
@patch('ai_tour_guide.knowledge_base.retrieval.EmbeddingSettings')
@patch('ai_tour_guide.knowledge_base.retrieval.Session')
@patch('ai_tour_guide.knowledge_base.retrieval.create_database_engine')
def test_vector_retrieval_embeds_once_and_passes_metadata(
    create_engine: MagicMock,
    session_class: MagicMock,
    settings_class: MagicMock,
    embedder_class: MagicMock,
    search_vector: MagicMock,
) -> None:
    engine = MagicMock()
    session = MagicMock(spec=Session)
    create_engine.return_value = engine
    session_class.return_value.__enter__.return_value = session
    settings_class.return_value = _settings()
    embedder_class.return_value.embed_query.return_value = np.array([0.1, 0.2])
    chunks = [MagicMock()]
    search_vector.return_value = chunks

    assert retrieve('Brittany coast', mode='vector', k=2) == chunks

    embedder_class.return_value.embed_query.assert_called_once_with('Brittany coast')
    search_vector.assert_called_once_with(
        session,
        [0.1, 0.2],
        2,
        embedding_metadata=embedder_class.return_value.metadata,
    )
    engine.dispose.assert_called_once_with()


@patch('ai_tour_guide.knowledge_base.retrieval.search_text')
@patch('ai_tour_guide.knowledge_base.retrieval.FastEmbedder')
@patch('ai_tour_guide.knowledge_base.retrieval.Session')
@patch('ai_tour_guide.knowledge_base.retrieval.create_database_engine')
def test_text_retrieval_does_not_embed(
    create_engine: MagicMock,
    session_class: MagicMock,
    embedder_class: MagicMock,
    search_text: MagicMock,
) -> None:
    engine = MagicMock()
    session = MagicMock(spec=Session)
    create_engine.return_value = engine
    session_class.return_value.__enter__.return_value = session
    chunks = [MagicMock()]
    search_text.return_value = chunks

    assert retrieve('Brittany coast', mode='text', k=2) == chunks

    embedder_class.assert_not_called()
    search_text.assert_called_once_with(session, 'Brittany coast', 2)
    engine.dispose.assert_called_once_with()


@patch('ai_tour_guide.knowledge_base.retrieval.search_text')
@patch('ai_tour_guide.knowledge_base.retrieval.search_vector')
@patch('ai_tour_guide.knowledge_base.retrieval.FastEmbedder')
@patch('ai_tour_guide.knowledge_base.retrieval.EmbeddingSettings')
@patch('ai_tour_guide.knowledge_base.retrieval.Session')
@patch('ai_tour_guide.knowledge_base.retrieval.create_database_engine')
def test_hybrid_retrieval_combines_rankings(
    create_engine: MagicMock,
    session_class: MagicMock,
    settings_class: MagicMock,
    embedder_class: MagicMock,
    search_vector: MagicMock,
    search_text: MagicMock,
) -> None:
    engine = MagicMock()
    session = MagicMock(spec=Session)
    create_engine.return_value = engine
    session_class.return_value.__enter__.return_value = session
    settings_class.return_value = _settings()
    embedder_class.return_value.embed_query.return_value = np.array([0.1, 0.2])
    vector_chunk = MagicMock(chunk_id='vector')
    shared_chunk = MagicMock(chunk_id='shared')
    text_chunk = MagicMock(chunk_id='text')
    search_vector.return_value = [shared_chunk, vector_chunk]
    search_text.return_value = [shared_chunk, text_chunk]

    result = retrieve(
        'Brittany coast',
        mode='hybrid',
        k=3,
        hybrid_settings=HybridSearchSettings(vector_weight=0, text_weight=1),
    )

    assert result == [shared_chunk, text_chunk, vector_chunk]
    search_vector.assert_called_once()
    search_text.assert_called_once_with(session, 'Brittany coast', 3)
    engine.dispose.assert_called_once_with()


def test_retrieval_rejects_an_unsupported_mode() -> None:
    with pytest.raises(ValueError, match='Unsupported search mode'):
        retrieve('Brittany coast', mode='invalid')  # type: ignore[arg-type]


def test_search_mode_lists_all_supported_modes() -> None:
    assert [mode.value for mode in SearchMode] == ['vector', 'text', 'hybrid']


def test_hybrid_search_settings_have_explicit_defaults() -> None:
    settings = HybridSearchSettings()

    assert settings.vector_weight == 1.0
    assert settings.text_weight == 1.0
    assert settings.rank_constant == DEFAULT_RRF_RANK_CONSTANT == 60


@pytest.mark.parametrize(
    'kwargs',
    [
        {'vector_weight': -1},
        {'text_weight': -1},
        {'vector_weight': 0, 'text_weight': 0},
        {'rank_constant': -1},
    ],
)
def test_hybrid_search_settings_reject_invalid_values(kwargs) -> None:
    with pytest.raises(ValueError):
        HybridSearchSettings(**kwargs)


@patch('ai_tour_guide.knowledge_base.retrieval.Session')
@patch('ai_tour_guide.knowledge_base.retrieval.create_database_engine')
def test_retrieval_disposes_engine_when_search_fails(
    create_engine: MagicMock,
    session_class: MagicMock,
) -> None:
    engine = MagicMock()
    create_engine.return_value = engine
    session = MagicMock(spec=Session)
    session_class.return_value.__enter__.return_value = session

    with (
        patch(
            'ai_tour_guide.knowledge_base.retrieval.search_text',
            side_effect=RuntimeError('database unavailable'),
        ),
        pytest.raises(RuntimeError, match='database unavailable'),
    ):
        retrieve('Brittany coast', mode='text')

    engine.dispose.assert_called_once_with()
