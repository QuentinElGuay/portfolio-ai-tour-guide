from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sqlalchemy.orm import Session

from ai_tour_guide.knowledge_base.retrieval import (
    DEFAULT_RRF_RANK_CONSTANT,
    HybridSearchSettings,
    RetrievedChunk,
    ScoreKind,
    SearchMode,
    SiblingChunks,
    SourceMetadata,
    retrieve,
    retrieve_siblings,
)
from ai_tour_guide.knowledge_base.search import ScoredDocumentChunk


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.model_name = 'test-model'
    settings.normalize = True
    settings.cache_dir = None
    return settings


def _chunk(chunk_id: str):
    return SimpleNamespace(
        document_id=7,
        chunk_id=chunk_id,
        section_path=['Brittany', 'Coast'],
        section_id='section-1',
        section_chunk_index=0,
        chunk_index=0,
        text=f'Text for {chunk_id}.',
        page_start=2,
        page_end=3,
        document=SimpleNamespace(
            title='A guide to Brittany',
            source_url='https://example.com/brittany',
            publisher='Tourism Board',
            publication_date=date(2026, 1, 2),
            collection='tour-guides',
            version='2026',
        ),
    )


def _source(chunk_id: str) -> SourceMetadata:
    return SourceMetadata(
        document_id=7,
        chunk_id=chunk_id,
        title='A guide to Brittany',
        source_url='https://example.com/brittany',
        publisher='Tourism Board',
        publication_date=date(2026, 1, 2),
        collection='tour-guides',
        version='2026',
        section_path=('Brittany', 'Coast'),
        page_start=2,
        page_end=3,
    )


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
    embedder_class.return_value.metadata.distance_metric = 'cosine'
    chunk = _chunk('chunk-1')
    search_vector.return_value = [ScoredDocumentChunk(chunk=chunk, score=0.2)]

    result = retrieve(
        'Brittany coast',
        mode='vector',
        k=2,
        retrieve_siblings=False,
    )

    embedder_class.return_value.embed_query.assert_called_once_with('Brittany coast')
    assert result == [
        RetrievedChunk(
            chunk=chunk,
            rank=1,
            score=0.8,
            score_kind=ScoreKind.COSINE_SIMILARITY,
            source=_source('chunk-1'),
        )
    ]
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
    chunk = _chunk('chunk-1')
    search_text.return_value = [ScoredDocumentChunk(chunk=chunk, score=0.7)]

    assert retrieve(
        'Brittany coast',
        mode='text',
        k=2,
        retrieve_siblings=False,
    ) == [
        RetrievedChunk(
            chunk=chunk,
            rank=1,
            score=0.7,
            score_kind=ScoreKind.TEXT_RANK,
            source=_source('chunk-1'),
        )
    ]

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
    embedder_class.return_value.metadata.distance_metric = 'cosine'
    vector_chunk = _chunk('vector')
    shared_chunk = _chunk('shared')
    text_chunk = _chunk('text')
    search_vector.return_value = [
        ScoredDocumentChunk(chunk=shared_chunk, score=0.1),
        ScoredDocumentChunk(chunk=vector_chunk, score=0.2),
    ]
    search_text.return_value = [
        ScoredDocumentChunk(chunk=shared_chunk, score=0.9),
        ScoredDocumentChunk(chunk=text_chunk, score=0.8),
    ]

    result = retrieve(
        'Brittany coast',
        mode='hybrid',
        k=3,
        hybrid_settings=HybridSearchSettings(vector_weight=0, text_weight=1),
        retrieve_siblings=False,
    )

    assert [item.chunk for item in result] == [shared_chunk, text_chunk, vector_chunk]
    assert all(item.score_kind is ScoreKind.RRF for item in result)
    search_vector.assert_called_once()
    search_text.assert_called_once_with(session, 'Brittany coast', 3)
    engine.dispose.assert_called_once_with()


@patch('ai_tour_guide.knowledge_base.retrieval.retrieve_siblings')
@patch('ai_tour_guide.knowledge_base.retrieval.search_text')
@patch('ai_tour_guide.knowledge_base.retrieval.Session')
@patch('ai_tour_guide.knowledge_base.retrieval.create_database_engine')
def test_retrieval_expands_search_results_with_siblings(
    create_engine: MagicMock,
    session_class: MagicMock,
    search_text: MagicMock,
    retrieve_siblings_mock: MagicMock,
) -> None:
    engine = MagicMock()
    session = MagicMock(spec=Session)
    create_engine.return_value = engine
    session_class.return_value.__enter__.return_value = session
    matched_chunk = _chunk('matched')
    first_sibling = _chunk('first')
    first_sibling.section_chunk_index = 0
    matched_chunk.section_chunk_index = 1
    search_text.return_value = [ScoredDocumentChunk(chunk=matched_chunk, score=0.7)]
    retrieve_siblings_mock.return_value = SiblingChunks(
        section_id='section-1',
        chunks=(first_sibling, matched_chunk),
    )

    result = retrieve('Brittany coast', mode='text', k=2)

    assert result[0].section_id == 'section-1'
    assert result[0].text == 'Text for first.\n\nText for matched.'
    retrieve_siblings_mock.assert_called_once_with(session, matched_chunk)


def test_retrieve_siblings_returns_document_scoped_ordered_text() -> None:
    session = MagicMock(spec=Session)
    chunk = _chunk('matched')
    first_sibling = _chunk('first')
    first_sibling.section_chunk_index = 0
    chunk.section_chunk_index = 1
    session.scalars.return_value.all.return_value = [first_sibling, chunk]

    siblings = retrieve_siblings(session, chunk)

    assert siblings.section_id == 'section-1'
    assert siblings.chunks == (first_sibling, chunk)
    assert siblings.text == 'Text for first.\n\nText for matched.'


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
