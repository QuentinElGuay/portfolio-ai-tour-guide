import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ai_tour_guide.app.agent.demo_questions import DEMO_WELCOME_MESSAGE
from ai_tour_guide.app.chat.backends import (
    DEFAULT_CHAT_API_TIMEOUT_SECONDS,
    DemoBackend,
    DemoResponseDelay,
    HttpChatBackend,
    demo_response_delay_from_environment,
)
from ai_tour_guide.app.chat.models import FREE_TEXT_INPUT_ID


def test_demo_backend_starts_and_sends_without_client_history() -> None:
    async def exercise() -> None:
        backend = DemoBackend()
        started = await backend.start_chat()
        response = await backend.send_message(
            str(started.session_id),
            str(started.step_id),
            'identity',
        )

        assert started.step_id == 'welcome'
        assert started.message == DEMO_WELCOME_MESSAGE
        assert [button.input_id for button in started.buttons] == [
            'identity',
            'destinations',
        ]
        assert response.step_id == 'identity'
        assert 'Petit Guide' in response.message

    asyncio.run(exercise())


def test_demo_backend_handles_free_text_as_a_first_class_input() -> None:
    async def exercise() -> None:
        backend = DemoBackend()
        started = await backend.start_chat()
        response = await backend.send_message(
            str(started.session_id),
            str(started.step_id),
            FREE_TEXT_INPUT_ID,
            'What should I visit?',
        )
        assert response.step_id == 'welcome'
        assert response.message

    asyncio.run(exercise())


def test_demo_response_delay_reads_chat_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('CHAT_DEMO_RESPONSE_DELAY_MIN_SECONDS', '2.25')
    monkeypatch.setenv('CHAT_DEMO_RESPONSE_DELAY_MAX_SECONDS', '2.75')

    assert demo_response_delay_from_environment() == DemoResponseDelay(2.25, 2.75)


def test_http_backend_allows_time_for_a_complete_chat_turn() -> None:
    backend = HttpChatBackend('http://agent/chat')

    assert backend.timeout.read == DEFAULT_CHAT_API_TIMEOUT_SECONDS


@patch('ai_tour_guide.app.chat.backends.asyncio.sleep', new_callable=AsyncMock)
@patch('ai_tour_guide.app.chat.backends.random.uniform', return_value=2.5)
@patch('ai_tour_guide.app.chat.backends.httpx.AsyncClient')
def test_http_demo_backend_delays_a_successful_response(
    async_client: MagicMock,
    random_uniform: MagicMock,
    sleep: AsyncMock,
) -> None:
    response = MagicMock()
    response.json.return_value = {
        'session_id': '12345678-1234-5678-1234-567812345678',
        'step_id': 'welcome',
        'message': 'Answer.',
        'buttons': [],
        'request_id': None,
    }
    client = AsyncMock()
    client.post.return_value = response
    async_client.return_value.__aenter__.return_value = client

    asyncio.run(
        HttpChatBackend(
            'http://agent/chat',
            demo_response_delay=DemoResponseDelay(2.0, 3.0),
        ).send_message(
            '12345678-1234-5678-1234-567812345678',
            'welcome',
            FREE_TEXT_INPUT_ID,
            'Where should I go?',
        )
    )

    random_uniform.assert_called_once_with(2.0, 3.0)
    sleep.assert_awaited_once_with(2.5)


@patch('ai_tour_guide.app.chat.backends.httpx.AsyncClient')
def test_http_backend_posts_start_and_parses_conversation_response(
    async_client: MagicMock,
) -> None:
    response = MagicMock()
    response.json.return_value = {
        'session_id': '12345678-1234-5678-1234-567812345678',
        'step_id': 'welcome',
        'message': 'Welcome.',
        'buttons': [],
        'request_id': None,
    }
    client = AsyncMock()
    client.post.return_value = response
    async_client.return_value.__aenter__.return_value = client

    result = asyncio.run(HttpChatBackend('http://agent/chat').start_chat())

    assert result.message == 'Welcome.'
    client.post.assert_awaited_once_with('http://agent/chat/start', json={})


@patch('ai_tour_guide.app.chat.backends.httpx.AsyncClient')
def test_http_backend_sends_only_current_session_state(
    async_client: MagicMock,
) -> None:
    response = MagicMock()
    response.json.return_value = {
        'session_id': '12345678-1234-5678-1234-567812345678',
        'step_id': 'welcome',
        'message': 'Answer.',
        'buttons': [],
        'request_id': None,
    }
    client = AsyncMock()
    client.post.return_value = response
    async_client.return_value.__aenter__.return_value = client

    asyncio.run(
        HttpChatBackend('http://agent/chat').send_message(
            '12345678-1234-5678-1234-567812345678',
            'welcome',
            FREE_TEXT_INPUT_ID,
            'Where should I go?',
        )
    )

    client.post.assert_awaited_once_with(
        'http://agent/chat/message',
        json={
            'session_id': '12345678-1234-5678-1234-567812345678',
            'expected_step_id': 'welcome',
            'input_id': FREE_TEXT_INPUT_ID,
            'text': 'Where should I go?',
        },
    )


@patch('ai_tour_guide.app.chat.backends.httpx.AsyncClient')
def test_http_backend_hides_transport_error_details(
    async_client: MagicMock,
) -> None:
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        'secret provider details',
        request=httpx.Request('POST', 'http://agent/chat/message'),
        response=httpx.Response(503),
    )
    client = AsyncMock()
    client.post.return_value = response
    async_client.return_value.__aenter__.return_value = client

    with pytest.raises(RuntimeError) as error:
        asyncio.run(
            HttpChatBackend('http://agent/chat').send_message(
                '12345678-1234-5678-1234-567812345678',
                'welcome',
                FREE_TEXT_INPUT_ID,
                'Where should I go?',
            )
        )

    assert 'secret provider details' not in str(error.value)
    assert 'temporarily unavailable' in str(error.value)


@patch('ai_tour_guide.app.chat.backends.httpx.AsyncClient')
def test_http_backend_submits_feedback_under_chat_namespace(
    async_client: MagicMock,
) -> None:
    response = MagicMock()
    response.json.return_value = {'request_id': '12345678-1234-5678-1234-567812345678'}
    client = AsyncMock()
    client.post.return_value = response
    async_client.return_value.__aenter__.return_value = client

    asyncio.run(
        HttpChatBackend('http://agent/chat').submit_feedback(
            '12345678-1234-5678-1234-567812345678', False
        )
    )

    client.post.assert_awaited_once_with(
        'http://agent/chat/feedback',
        json={
            'message_id': '12345678-1234-5678-1234-567812345678',
            'helpful': False,
            'comment': None,
        },
    )
