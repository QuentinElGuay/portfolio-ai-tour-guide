from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from pydantic import ValidationError

from ai_tour_guide.agent.api import AskRequest, SourceResponse, ask, health
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGResult, SourceReference
from ai_tour_guide.knowledge_base.search import SearchMode


@patch('ai_tour_guide.agent.api._ensure_knowledge_base_ready')
def test_health_reports_ok(_ensure_knowledge_base_ready: MagicMock) -> None:
    _ensure_knowledge_base_ready.return_value = None
    assert health() == {'status': 'ok'}


@patch('ai_tour_guide.agent.api.answer_question')
def test_ask_returns_the_answer_and_sources(answer_question: MagicMock) -> None:
    """Verify that the ask endpoint returns the generated answer with its source references."""
    answer_question.return_value = RAGResult(
        question='Where?',
        mode=SearchMode.HYBRID,
        k=5,
        messages=(),
        generated=GeneratedAnswer('The answer.'),
        sources=(
            SourceReference(
                source_url='https://example.test/guide',
                version='2026',
                title='Guide',
                publisher=None,
                collection=None,
                publication_date=None,
                pages=(4, 5),
            ),
        ),
    )

    response = ask(AskRequest(question='  Where?  '))

    assert response.answer == 'The answer.'
    assert isinstance(response.request_id, UUID)
    assert response.request_id == answer_question.return_value.request_id
    assert response.sources == [
        SourceResponse(
            source_url='https://example.test/guide',
            version='2026',
            title='Guide',
            publisher=None,
            collection=None,
            publication_date=None,
            pages=[4, 5],
        )
    ]
    answer_question.assert_called_once_with('Where?')


def test_ask_rejects_an_empty_question() -> None:
    """Verify that ask requests reject questions containing only whitespace."""
    with pytest.raises(ValidationError, match='question must not be empty'):
        AskRequest(question='  ')
