"""Tests for concrete retrieval strategy orchestration."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import numpy as np

from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.search.models import ScoreKind, SearchMode
from ai_tour_guide.knowledge_base.search.queries import ScoredDocumentChunk
from ai_tour_guide.knowledge_base.search.strategies import (
    HybridSearchStrategy,
    TextSearchStrategy,
    VectorSearchStrategy,
    _relevance_score,
    _score_kind,
    create_search_strategy,
)


def _scored(chunk_id: str, score: float) -> ScoredDocumentChunk:
    return ScoredDocumentChunk(
        chunk=cast(DocumentChunkRow, SimpleNamespace(chunk_id=chunk_id)), score=score
    )


@patch('ai_tour_guide.knowledge_base.search.strategies.search_text')
def test_text_strategy_assigns_rank_and_text_score_kind(search_text: MagicMock) -> None:
    """Verify that lexical results receive stable ranks and text-score metadata."""
    search_text.return_value = [_scored('one', 0.8), _scored('two', 0.4)]

    results = TextSearchStrategy().search(MagicMock(), 'coast', k=2)

    assert [
        (item.chunk.chunk_id, item.search.rank, item.search.score_kind)
        for item in results
    ] == [
        ('one', 1, ScoreKind.TEXT_RANK),
        ('two', 2, ScoreKind.TEXT_RANK),
    ]


@patch('ai_tour_guide.knowledge_base.search.strategies.search_vector')
def test_vector_strategy_embeds_query_and_converts_distance_to_relevance(
    search_vector: MagicMock,
) -> None:
    """Verify that vector retrieval uses the embedder and normalizes cosine distance."""
    embedder = MagicMock()
    embedder.embed_query.return_value = np.asarray([0.2, 0.8])
    embedder.metadata = EmbeddingMetadata(
        provider='test', model_name='model', dimensions=2, normalized=True
    )
    search_vector.return_value = [_scored('one', 0.25)]

    results = VectorSearchStrategy(embedder).search(MagicMock(), 'coast', k=1)

    assert results[0].search.score == 0.75
    assert results[0].search.score_kind is ScoreKind.COSINE_SIMILARITY
    assert search_vector.call_args.args[1:] == ([0.2, 0.8], 1)
    assert search_vector.call_args.kwargs['embedding_metadata'] is embedder.metadata


def test_hybrid_strategy_passes_weighted_rankings_to_fusion() -> None:
    """Verify that hybrid retrieval invokes both strategies before reciprocal-rank fusion."""
    vector = MagicMock()
    text = MagicMock()
    vector.search.return_value = ['vector']
    text.search.return_value = ['text']
    strategy = HybridSearchStrategy(
        vector, text, MagicMock(vector_weight=2, text_weight=1, rank_constant=60)
    )

    with patch(
        'ai_tour_guide.knowledge_base.search.strategies.reciprocal_rank_fusion',
        return_value=['fused'],
    ) as fusion:
        assert strategy.search(MagicMock(), 'coast', k=3) == ['fused']

    fusion.assert_called_once_with(
        [(['vector'], 2), (['text'], 1)], k=3, rank_constant=60
    )


def test_score_conversion_rejects_unknown_metrics() -> None:
    """Verify that unsupported distance metrics cannot produce misleading ranking metadata."""
    for function in (_score_kind, lambda metric: _relevance_score(0.5, metric)):
        try:
            function('unknown')
        except ValueError as exc:
            assert 'Unsupported embedding distance metric' in str(exc)
        else:
            raise AssertionError('Expected unsupported metric to fail')


@patch('ai_tour_guide.knowledge_base.search.strategies.get_cached_embedder')
def test_factory_builds_the_requested_strategy(get_cached_embedder: MagicMock) -> None:
    """Verify that strategy selection avoids embeddings for text and wires vector modes."""
    assert isinstance(create_search_strategy(SearchMode.TEXT), TextSearchStrategy)
    assert get_cached_embedder.call_count == 0
    assert isinstance(create_search_strategy(SearchMode.VECTOR), VectorSearchStrategy)
    assert isinstance(create_search_strategy(SearchMode.HYBRID), HybridSearchStrategy)
