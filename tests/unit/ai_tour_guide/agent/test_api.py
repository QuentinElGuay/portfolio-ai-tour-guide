import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

os.environ.setdefault('EMBEDDING_DIMENSIONS', '384')
os.environ.setdefault('EMBEDDING_MODEL_NAME', 'test-model')

from ai_tour_guide.agent.api import AskRequest, ask, health
from ai_tour_guide.agent.rag.models import Context, RAGResult


def test_health_reports_ok() -> None:
    assert health() == {'status': 'ok'}


@patch('ai_tour_guide.agent.api.answer_question')
def test_ask_returns_the_answer_and_sources(answer_question: MagicMock) -> None:
    answer_question.return_value = RAGResult(
        answer='Visit the museum in the morning.',
        contexts=(
            Context(
                section_id='activities-and-things-to-do-top-attractions-in-brittany-museums-and-galleries',
                text='Museum context',
                chunks=(
                    SimpleNamespace(
                        source=SimpleNamespace(
                            title='Museum guide',
                            page_start=4,
                            page_end=5,
                        )
                    ),
                ),
            ),
        ),
    )

    response = ask(AskRequest(question='  What should I visit?  '))

    assert response.model_dump() == {
        'answer': 'Visit the museum in the morning.',
        'sources': [
            {'title': 'Museum guide', 'page_start': 4, 'page_end': 5},
        ],
    }
    answer_question.assert_called_once_with('What should I visit?')


def test_ask_rejects_an_empty_question() -> None:
    with pytest.raises(ValidationError, match='question must not be empty'):
        AskRequest(question='   ')
