import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.api import (
    AskRequest,
    FeedbackRequest,
    SourceResponse,
    _ensure_knowledge_base_ready,
    app,
    ask,
    feedback,
    health,
)
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGResult, SourceReference
from ai_tour_guide.knowledge_base.search import SearchMode


def _post(path: str, payload: dict[str, object]) -> httpx.Response:
    """Send one request through the ASGI boundary without starting a server thread."""

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url='http://testserver'
        ) as client:
            return await client.post(path, json=payload)

    return asyncio.run(request())


@patch('ai_tour_guide.agent.api._ensure_knowledge_base_ready')
def test_health_reports_ok(_ensure_knowledge_base_ready: MagicMock) -> None:
    """Verify that health reports ok."""
    _ensure_knowledge_base_ready.return_value = None
    assert asyncio.run(health()) == {'status': 'ok'}


@patch('ai_tour_guide.agent.api.create_database_engine')
def test_health_logs_how_to_populate_an_empty_knowledge_base(
    create_database_engine: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that health logs how to populate an empty knowledge base."""
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
    """Verify that health logs when postgresql is unavailable."""
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
@patch('ai_tour_guide.agent.api._answer_question', new_callable=AsyncMock)
def test_ask_returns_the_answer_and_sources(
    answer_question: AsyncMock,
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

    response = asyncio.run(ask(AskRequest(question='  Where?  ')))

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
    answer_question.assert_awaited_once_with('Where?')
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
    """Verify that feedback stores a rating."""
    request_id = UUID('12345678-1234-5678-1234-567812345678')

    response = asyncio.run(
        feedback(
            FeedbackRequest(
                request_id=request_id,
                helpful=True,
                comment='  Accurate answer.  ',
            )
        )
    )

    assert response.request_id == request_id
    store_feedback.assert_called_once_with(request_id, True, 'Accurate answer.')


@patch('ai_tour_guide.agent.api.store_feedback', return_value=False)
def test_feedback_rejects_unknown_rag_result(store_feedback: MagicMock) -> None:
    """Verify that feedback rejects unknown rag result."""
    with pytest.raises(HTTPException, match='Unknown RAG result') as exc_info:
        asyncio.run(
            feedback(
                FeedbackRequest(
                    request_id=UUID('12345678-1234-5678-1234-567812345678'),
                    helpful=False,
                )
            )
        )

    assert exc_info.value.status_code == 404
    store_feedback.assert_called_once()


@patch('ai_tour_guide.agent.api._answer_question', new_callable=AsyncMock)
@patch('ai_tour_guide.agent.api.store_rag_result')
def test_ask_http_boundary_normalizes_question_and_serializes_response(
    store_rag_result: MagicMock,
    answer_question: AsyncMock,
) -> None:
    """Verify that POST /ask validates input and emits the public response schema."""
    result = RAGResult(
        question='Where?',
        mode=SearchMode.HYBRID,
        k=5,
        messages=(),
        generated=GeneratedAnswer('The answer.'),
    )
    answer_question.return_value = result

    response = _post('/ask', {'question': '  Where?  '})

    assert response.status_code == 200
    assert response.json() == {
        'schema_version': 1,
        'request_id': str(result.request_id),
        'answer': 'The answer.',
        'sources': [],
    }
    answer_question.assert_awaited_once_with('Where?')
    store_rag_result.assert_called_once_with(result.request_id, result.to_dict())


def test_ask_http_boundary_rejects_missing_or_blank_questions() -> None:
    """Verify that invalid request JSON becomes FastAPI's 422 validation response."""
    for payload in ({}, {'question': '   '}, {'question': 42}):
        response = _post('/ask', payload)
        assert response.status_code == 422


@patch('ai_tour_guide.agent.api.store_rag_result', side_effect=SQLAlchemyError())
@patch('ai_tour_guide.agent.api._answer_question', new_callable=AsyncMock)
def test_ask_http_boundary_returns_service_error_when_persistence_fails(
    answer_question: AsyncMock,
    _store_rag_result: MagicMock,
) -> None:
    """Verify that persistence failures do not return an untracked generated answer."""
    answer_question.return_value = RAGResult(
        question='Where?',
        mode=SearchMode.HYBRID,
        k=5,
        messages=(),
        generated=GeneratedAnswer('The answer.'),
    )

    response = _post('/ask', {'question': 'Where?'})

    assert response.status_code == 503
    assert (
        response.json()['detail']
        == 'Unable to store the generated answer for feedback.'
    )


@patch('ai_tour_guide.agent.api.store_feedback', return_value=False)
def test_feedback_http_boundary_serializes_unknown_request_as_not_found(
    store_feedback: MagicMock,
) -> None:
    """Verify that POST /feedback exposes unknown request IDs as HTTP 404."""
    request_id = '12345678-1234-5678-1234-567812345678'

    response = _post('/feedback', {'request_id': request_id, 'helpful': False})

    assert response.status_code == 404
    assert response.json()['detail'] == 'Unknown RAG result request ID.'
    store_feedback.assert_called_once()


def test_feedback_http_boundary_rejects_invalid_request_shape() -> None:
    """Verify that malformed feedback JSON does not call persistence."""
    response = _post('/feedback', {'request_id': 'not-a-uuid', 'helpful': 'yes'})

    assert response.status_code == 422
