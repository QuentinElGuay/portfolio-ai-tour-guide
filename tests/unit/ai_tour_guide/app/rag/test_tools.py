from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from ai_tour_guide.app.services.rag.tools import (
    RetrievalStatus,
    search_tourism_knowledge_base,
)
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search.models import (
    ScoreKind,
    SearchMetadata,
    SearchResult,
)


def _context() -> RetrievedContext:
    document = MagicMock(
        document_id=7,
        source_url='https://example.test/guide',
        title='Guide to Brittany',
        version='2026',
        publisher='Tourism Board',
        collection='Guides',
        publication_date=date(2026, 1, 2),
    )
    chunk = MagicMock(
        text='Take the train from Rennes.',
        document_id=7,
        section_id='transport',
        section_path=['Transport'],
        page_start=4,
        page_end=5,
        document=document,
    )
    result = SearchResult(
        chunk=chunk,
        search=SearchMetadata(1, 0.91, ScoreKind.TEXT_RANK),
    )
    return MagicMock(search_results=(result,))


def test_search_tool_returns_provenance_rich_evidence() -> None:
    with patch(
        'ai_tour_guide.app.services.rag.tools.retrieve_context',
        return_value=(_context(),),
    ):
        result = search_tourism_knowledge_base('  train travel  ')

    assert result.status is RetrievalStatus.SUCCESS
    assert result.query.query == 'train travel'
    evidence = result.evidence[0]
    assert evidence.source_url == 'https://example.test/guide'
    assert evidence.pages == (4, 5)
    assert evidence.section_path == ('Transport',)
    assert evidence.score == 0.91


def test_search_tool_distinguishes_empty_results() -> None:
    with patch(
        'ai_tour_guide.app.services.rag.tools.retrieve_context', return_value=()
    ):
        result = search_tourism_knowledge_base('unknown')

    assert result.status is RetrievalStatus.EMPTY
    assert result.evidence == ()
    assert result.error is None


def test_search_tool_returns_typed_retrieval_errors() -> None:
    with patch(
        'ai_tour_guide.app.services.rag.tools.retrieve_context',
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
