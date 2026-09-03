import asyncio
import logging
from collections.abc import Mapping
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.app.agent.rag.models import GeneratedAnswer, RAGResult
from ai_tour_guide.app.api import (
    _ensure_knowledge_base_ready,
    app,
    chat_message,
    health,
    start_chat,
)
from ai_tour_guide.app.chat.models import ChatMessageRequest, ConversationResponse
from ai_tour_guide.knowledge_base.search import SearchMode


@pytest.fixture(autouse=True)
def store_chat_message_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Prevent HTTP-boundary unit tests from writing conversation rows."""
    monkeypatch.setenv('AGENT_LLM_PROVIDER', 'openai')
    monkeypatch.setenv('AGENT_LLM_MODEL', 'test-model')
    stored = MagicMock()
    monkeypatch.setattr('ai_tour_guide.app.api.store_chat_message', stored)
    return stored


def _post(path: str, payload: Mapping[str, object]) -> httpx.Response:
    """Send one request through the ASGI boundary without starting a server thread."""

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url='http://testserver'
        ) as client:
            return await client.post(path, json=payload)

    return asyncio.run(request())


@patch('ai_tour_guide.app.api._ensure_knowledge_base_ready')
def test_health_reports_ok(_ensure_knowledge_base_ready: MagicMock) -> None:
    _ensure_knowledge_base_ready.return_value = None
    assert asyncio.run(health()) == {'status': 'ok'}


def test_chat_start_always_creates_a_new_renderable_session() -> None:
    first = asyncio.run(start_chat())
    second = asyncio.run(start_chat())

    assert isinstance(first, ConversationResponse)
    assert first.session_id != second.session_id
    assert first.step_id == 'welcome'
    assert first.message
    assert first.llm is not None
    assert first.llm.provider == 'openai'
    assert [button.input_id for button in first.buttons] == [
        'identity',
        'destinations',
    ]


@patch('ai_tour_guide.app.api.store_rag_result')
@patch('ai_tour_guide.app.api._answer_turn', new_callable=AsyncMock)
def test_chat_message_serializes_the_backend_response(
    answer_question: AsyncMock,
    store_rag_result: MagicMock,
) -> None:
    result = RAGResult(
        question='Where?',
        mode=SearchMode.HYBRID,
        k=5,
        messages=(),
        generated=GeneratedAnswer('The answer.'),
    )
    answer_question.return_value = result
    session = asyncio.run(start_chat())
    request = ChatMessageRequest(
        session_id=session.session_id,
        expected_step_id='welcome',
        input_id='FREE_TEXT',
        text='Where?',
    )

    response = asyncio.run(chat_message(request))

    payload = response.model_dump(mode='json')
    assert payload == {
        'session_id': str(request.session_id),
        'message_id': str(response.message_id),
        'step_id': 'welcome',
        'message': 'The answer.',
        'buttons': [
            {'input_id': 'identity', 'label': 'Tell me about you'},
            {'input_id': 'destinations', 'label': 'What destinations are covered?'},
        ],
        'request_id': str(result.request_id),
        'sources': [],
        'trace': {
            'intent': 'travel_question',
            'actions': ['refuse'],
            'tool_inputs': [],
            'tool_call_count': 0,
            'evidence_sufficient': False,
            'retries': 0,
            'final_status': 'refused',
        },
        'llm': {'provider': 'openai', 'model': 'test-model'},
    }
    store_rag_result.assert_called_once_with(result.request_id, result.to_dict())


def test_chat_start_http_boundary_returns_contract_fields() -> None:
    response = _post('/chat/start', {})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        'session_id',
        'message_id',
        'step_id',
        'message',
        'buttons',
        'request_id',
        'sources',
        'trace',
        'llm',
    }
    assert payload['step_id'] == 'welcome'
    assert payload['buttons'] == [
        {'input_id': 'identity', 'label': 'Tell me about you'},
        {'input_id': 'destinations', 'label': 'What destinations are covered?'},
    ]
    assert payload['request_id'] is None
    assert payload['sources'] == []
    assert payload['llm']['provider'] == 'openai'


@patch('ai_tour_guide.app.api.store_feedback', return_value=True)
def test_chat_feedback_http_boundary_uses_the_chat_namespace(
    store_feedback: MagicMock,
) -> None:
    message_id = UUID(int=1)
    response = _post(
        '/chat/feedback',
        {'message_id': str(message_id), 'helpful': True, 'comment': '  Useful. '},
    )

    assert response.status_code == 200
    assert response.json() == {'message_id': str(message_id)}
    store_feedback.assert_called_once_with(message_id, True, 'Useful.')


@patch(
    'ai_tour_guide.app.agent.conversation.list_indexed_destinations',
    return_value=('Brittany', 'Normandy'),
)
def test_chat_message_catalog_is_deterministic(
    list_titles: MagicMock,
) -> None:
    session = asyncio.run(start_chat())
    response = asyncio.run(
        chat_message(
            ChatMessageRequest(
                session_id=session.session_id,
                expected_step_id='welcome',
                input_id='destinations',
            )
        )
    )

    assert (
        response.message
        == 'Our currently covered destinations are:\n- Brittany\n- Normandy'
    )
    assert response.step_id == 'destinations'
    assert response.request_id is None
    list_titles.assert_called_once_with()


def test_chat_message_rejects_unknown_and_stale_sessions() -> None:
    unknown = asyncio.run(
        _chat_message_error(
            ChatMessageRequest(
                session_id=UUID(int=999),
                expected_step_id='welcome',
                input_id='identity',
            )
        )
    )
    session = asyncio.run(start_chat())
    stale = asyncio.run(
        _chat_message_error(
            ChatMessageRequest(
                session_id=session.session_id,
                expected_step_id='identity',
                input_id='identity',
            )
        )
    )

    assert unknown.status_code == 404
    assert cast(dict[str, object], unknown.detail)['code'] == 'invalid_session'
    assert stale.status_code == 409
    assert cast(dict[str, object], stale.detail)['code'] == 'stale_expected_step_id'


async def _chat_message_error(request: ChatMessageRequest) -> HTTPException:
    with pytest.raises(HTTPException) as error:
        await chat_message(request)
    return error.value


@patch('ai_tour_guide.app.api.create_database_engine')
def test_health_allows_an_empty_knowledge_base_and_logs_how_to_populate_it(
    create_database_engine: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = create_database_engine.return_value
    engine.connect.return_value.__enter__.return_value.scalar.return_value = None

    with caplog.at_level(logging.WARNING):
        _ensure_knowledge_base_ready()

    assert 'make ingest' in caplog.messages[-1]
    assert 'make load-corpus' in caplog.messages[-1]
    engine.dispose.assert_called_once_with()


@patch('ai_tour_guide.app.api.create_database_engine')
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
