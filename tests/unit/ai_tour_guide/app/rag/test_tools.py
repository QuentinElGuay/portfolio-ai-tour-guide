"""Compatibility coverage for the shared tourism retrieval tool."""

from unittest.mock import MagicMock, patch

import pytest

from ai_tour_guide.app.services.rag.tools import (
    RetrievalQualitySettings,
    RetrievalStatus,
    search_tourism_knowledge_base,
)
from ai_tour_guide.knowledge_base.search.models import (
    ScoreKind,
    SearchMetadata,
    SearchResult,
)


def _context(
    *,
    rank: int = 1,
    score: float = 0.91,
    score_kind: ScoreKind = ScoreKind.TEXT_RANK,
):
    document = MagicMock(
        document_id=7,
        source_url='https://example.test/guide',
        title='Guide to Brittany',
        version='2026',
        publisher='Tourism Board',
        collection='Guides',
        publication_date=None,
    )
    chunk = MagicMock(
        document_id=7,
        section_id='transport',
        section_path=['Transport'],
        document=document,
    )
    result = SearchResult(
        chunk=chunk,
        search=SearchMetadata(rank, score, score_kind),
    )
    return MagicMock(
        source_document=document,
        section_id='transport',
        section_path=('Transport',),
        text='Take the train from Rennes.\n\nThe station is central.',
        pages=(4, 5),
        search_results=(result,),
    )


def test_search_tool_returns_one_provenance_rich_logical_context() -> None:
    context = _context()
    with patch(
        'ai_tour_guide.knowledge_base.retrieval.tool.retrieve_context',
        return_value=(context,),
    ):
        result = search_tourism_knowledge_base('  train travel  ')

    assert result.status is RetrievalStatus.SUCCESS
    assert result.query.query == 'train travel'
    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert evidence.source_url == 'https://example.test/guide'
    assert evidence.pages == (4, 5)
    assert evidence.section_path == ('Transport',)
    assert evidence.score == 0.91
    assert evidence.text == 'Take the train from Rennes.\n\nThe station is central.'
    assert result.contexts == (context,)


def test_search_tool_distinguishes_empty_results() -> None:
    with patch(
        'ai_tour_guide.knowledge_base.retrieval.tool.retrieve_context', return_value=()
    ):
        result = search_tourism_knowledge_base('unknown')

    assert result.status is RetrievalStatus.EMPTY
    assert result.evidence == ()
    assert result.low_confidence_evidence == ()
    assert result.error is None


def test_search_tool_returns_typed_retrieval_errors() -> None:
    with patch(
        'ai_tour_guide.knowledge_base.retrieval.tool.retrieve_context',
        side_effect=RuntimeError('database unavailable'),
    ):
        result = search_tourism_knowledge_base('train')

    assert result.status is RetrievalStatus.ERROR
    assert result.error is not None
    assert result.error.error_type == 'RuntimeError'
    assert result.error.message == 'database unavailable'


@pytest.mark.parametrize('query', ['', '   '])
def test_search_tool_rejects_invalid_queries(query: str) -> None:
    with pytest.raises(ValueError, match='query must not be empty'):
        search_tourism_knowledge_base(query)


def test_search_tool_keeps_low_confidence_contexts_out_of_llm_evidence() -> None:
    with patch(
        'ai_tour_guide.knowledge_base.retrieval.tool.retrieve_context',
        return_value=(_context(score=0.4, score_kind=ScoreKind.COSINE_SIMILARITY),),
    ):
        result = search_tourism_knowledge_base('train')

    assert result.status is RetrievalStatus.LOW_CONFIDENCE
    assert result.evidence == ()
    assert len(result.low_confidence_evidence) == 1
    assert result.all_evidence == result.low_confidence_evidence
    assert len(result.low_confidence_contexts) == 1


def test_search_tool_applies_score_kind_specific_thresholds() -> None:
    low_text = _context(rank=1, score=0.04, score_kind=ScoreKind.TEXT_RANK)
    high_vector = _context(rank=2, score=0.7, score_kind=ScoreKind.COSINE_SIMILARITY)
    with patch(
        'ai_tour_guide.knowledge_base.retrieval.tool.retrieve_context',
        return_value=(high_vector, low_text),
    ):
        result = search_tourism_knowledge_base(
            'train',
            quality_settings=RetrievalQualitySettings(
                minimum_cosine_similarity=0.65,
                minimum_text_rank=0.05,
            ),
        )

    assert result.status is RetrievalStatus.SUCCESS
    assert [evidence.score for evidence in result.evidence] == [0.7]
    assert [evidence.score for evidence in result.low_confidence_evidence] == [0.04]
    assert [evidence.rank for evidence in result.all_evidence] == [1, 2]


def test_search_tool_uses_the_best_matched_chunk_for_a_logical_context() -> None:
    context = _context(rank=3)
    primary = SearchResult(
        chunk=context.search_results[0].chunk,
        search=SearchMetadata(1, 0.95, ScoreKind.TEXT_RANK),
    )
    context.search_results = (*context.search_results, primary)
    with patch(
        'ai_tour_guide.knowledge_base.retrieval.tool.retrieve_context',
        return_value=(context,),
    ):
        result = search_tourism_knowledge_base('train')

    assert result.evidence[0].rank == 1
    assert result.evidence[0].score == 0.95
