import logging
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.api import (
    AskRequest,
    FeedbackRequest,
    SourceResponse,
    _ensure_knowledge_base_ready,
    ask,
    feedback,
    health,
)
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGResult, SourceReference
from ai_tour_guide.knowledge_base.search import SearchMode


@patch('ai_tour_guide.agent.api._ensure_knowledge_base_ready')
def test_health_reports_ok(_ensure_knowledge_base_ready: MagicMock) -> None:
    _ensure_knowledge_base_ready.return_value = None
    assert health() == {'status': 'ok'}


@patch('ai_tour_guide.agent.api.create_database_engine')
def test_health_logs_how_to_populate_an_empty_knowledge_base(
    create_database_engine: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = create_database_engine.return_value
    engine.connect.return_value.__enter__.return_value.scalar.return_value = None

    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(HTTPException, match='knowledge base is empty') as exc_info,
    ):
        _ensure_knowledge_base_ready()

    assert exc_info.value.status_code == 503
    assert 'make ingest' in exc_info.value.detail
    assert 'make load-corpus DB_SCHEMA=public' in caplog.messages[-1]
    engine.dispose.assert_called_once_with()


@patch('ai_tour_guide.agent.api.create_database_engine')
def test_health_logs_when_postgresql_is_unavailable(
    create_database_engine: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = create_database_engine.return_value
    engine.connect.side_effect = SQLAlchemyError('connection refused')

    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(HTTPException, match='knowledge base is unavailable') as exc_info,
    ):
        _ensure_knowledge_base_ready()

    assert exc_info.value.status_code == 503
    assert 'PostgreSQL is unavailable' in caplog.messages[-1]
    engine.dispose.assert_called_once_with()


@patch('ai_tour_guide.agent.api.store_rag_result')
@patch('ai_tour_guide.agent.api.answer_question')
def test_ask_returns_the_answer_and_sources(
    answer_question: MagicMock,
    store_rag_result: MagicMock,
) -> None:
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
    store_rag_result.assert_called_once_with(
        answer_question.return_value.request_id,
        answer_question.return_value.to_dict(),
    )


def test_ask_rejects_an_empty_question() -> None:
    """Verify that ask requests reject questions containing only whitespace."""
    with pytest.raises(ValidationError, match='question must not be empty'):
        AskRequest(question='  ')


@patch('ai_tour_guide.agent.api.store_feedback', return_value=True)
def test_feedback_stores_a_rating(store_feedback: MagicMock) -> None:
    request_id = UUID('12345678-1234-5678-1234-567812345678')

    response = feedback(
        FeedbackRequest(
            request_id=request_id,
            helpful=True,
            comment='  Accurate answer.  ',
        )
    )

    assert response.request_id == request_id
    store_feedback.assert_called_once_with(request_id, True, 'Accurate answer.')


@patch('ai_tour_guide.agent.api.store_feedback', return_value=False)
def test_feedback_rejects_unknown_rag_result(store_feedback: MagicMock) -> None:
    with pytest.raises(HTTPException, match='Unknown RAG result') as exc_info:
        feedback(
            FeedbackRequest(
                request_id=UUID('12345678-1234-5678-1234-567812345678'),
                helpful=False,
            )
        )

    assert exc_info.value.status_code == 404
    store_feedback.assert_called_once()
