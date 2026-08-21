import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ai_tour_guide.agent.chat.backends import DemoBackend, HttpChatBackend
from ai_tour_guide.agent.chat.models import Message, Role
from ai_tour_guide.agent.responses import NO_BACKEND_AVAILABLE_ANSWER


def test_demo_backend_returns_structured_fallback() -> None:
    """Verify that demo backend returns structured fallback."""
    result = asyncio.run(DemoBackend().ask([]))
    assert result['answer'] == NO_BACKEND_AVAILABLE_ANSWER
    assert result['sources'] == []


def test_demo_backend_feedback_is_a_noop() -> None:
    """Verify that demo backend feedback is a noop."""
    asyncio.run(DemoBackend().submit_feedback('TODO: request_id:1', True))


@patch('ai_tour_guide.agent.chat.backends.httpx.AsyncClient')
def test_http_backend_returns_validated_api_payload(async_client: MagicMock) -> None:
    """Verify that http backend returns validated api payload."""
    response = MagicMock()
    response.json.return_value = {
        'schema_version': 1,
        'answer': 'Visit.',
        'sources': [],
    }
    client = AsyncMock()
    client.post.return_value = response
    async_client.return_value.__aenter__.return_value = client
    messages: list[Message] = [{'role': Role.USER, 'content': 'What should I visit?'}]
    assert (
        asyncio.run(HttpChatBackend('http://agent/ask').ask(messages))
        == response.json.return_value
    )


@patch('ai_tour_guide.agent.chat.backends.httpx.AsyncClient')
def test_http_backend_submits_feedback(async_client: MagicMock) -> None:
    """Verify that http backend submits feedback."""
    response = MagicMock()
    client = AsyncMock()
    client.post.return_value = response
    async_client.return_value.__aenter__.return_value = client

    asyncio.run(
        HttpChatBackend('http://agent/ask').submit_feedback(
            '12345678-1234-5678-1234-567812345678',
            False,
        )
    )

    client.post.assert_awaited_once_with(
        'http://agent/feedback',
        json={
            'request_id': '12345678-1234-5678-1234-567812345678',
            'helpful': False,
            'comment': None,
        },
    )
    response.raise_for_status.assert_called_once_with()
