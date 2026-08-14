import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ai_tour_guide.agent.chat.backends import DemoBackend, HttpChatBackend
from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.responses import NO_BACKEND_AVAILABLE_ANSWER


def test_demo_backend_returns_structured_fallback() -> None:
    result = asyncio.run(DemoBackend().ask([]))
    assert result['answer'] == NO_BACKEND_AVAILABLE_ANSWER
    assert result['sources'] == []


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
