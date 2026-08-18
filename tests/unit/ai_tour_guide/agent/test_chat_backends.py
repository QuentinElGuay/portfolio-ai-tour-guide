import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ai_tour_guide.agent.chat.backends import DemoBackend, HttpChatBackend
from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.responses import NO_BACKEND_AVAILABLE_ANSWER


def test_demo_backend_returns_structured_fallback() -> None:
    result = asyncio.run(DemoBackend().ask([]))
    assert result['answer'] == NO_BACKEND_AVAILABLE_ANSWER
    assert result['sources'] == []


def test_demo_backend_feedback_is_a_noop() -> None:
    asyncio.run(DemoBackend().submit_feedback('TODO: request_id:1', True))


@patch('ai_tour_guide.agent.chat.backends.httpx.AsyncClient')
def test_http_backend_returns_validated_api_payload(async_client: MagicMock) -> None:
    response = MagicMock()
    response.json.return_value = {
        'schema_version': 1,
        'answer': 'Visit.',
        'sources': [],
    }
    client = AsyncMock()
    client.post.return_value = response
    async_client.return_value.__aenter__.return_value = client
    messages: list[Message] = [{'role': 'user', 'content': 'What should I visit?'}]
    assert (
        asyncio.run(HttpChatBackend('http://agent/ask').ask(messages))
        == response.json.return_value
    )


@patch('ai_tour_guide.agent.chat.backends.httpx.AsyncClient')
def test_http_backend_feedback_is_a_noop(async_client: MagicMock) -> None:
    asyncio.run(
        HttpChatBackend('http://agent/ask').submit_feedback('TODO: request_id:1', False)
    )
    async_client.assert_not_called()
