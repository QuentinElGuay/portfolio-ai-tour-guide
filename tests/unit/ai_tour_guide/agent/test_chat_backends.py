import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_tour_guide.agent.chat.backends import (
    DemoBackend,
    HttpChatBackend,
    _format_pages,
    create_backend,
)
from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.responses import LLM_CONFIGURATION_REQUIRED_ANSWER


def test_create_backend_uses_the_configured_agent_api(monkeypatch) -> None:
    monkeypatch.setenv('CHAT_API_URL', 'http://agent:8000/ask')

    backend = create_backend()

    assert isinstance(backend, HttpChatBackend)
    assert backend.api_url == 'http://agent:8000/ask'


def test_create_backend_requires_the_agent_api(monkeypatch) -> None:
    monkeypatch.delenv('CHAT_API_URL', raising=False)

    with pytest.raises(RuntimeError, match='CHAT_API_URL is required'):
        create_backend()


def test_demo_backend_requires_llm_configuration() -> None:
    messages: list[Message] = [
        {'role': 'user', 'content': 'What should I visit?'},
    ]

    result = asyncio.run(DemoBackend().generate_reply(messages))

    assert result == LLM_CONFIGURATION_REQUIRED_ANSWER


def test_format_pages_uses_singular_plural_and_natural_separators() -> None:
    assert _format_pages([31]) == 'page 31'
    assert _format_pages([31, 32]) == 'pages 31 and 32'
    assert _format_pages([31, 32, 33]) == 'pages 31, 32 and 33'


@patch('ai_tour_guide.agent.chat.backends.httpx.AsyncClient')
def test_http_backend_sends_the_latest_question_and_deduplicates_sources(
    async_client: MagicMock,
) -> None:
    response = MagicMock()
    response.json.return_value = {
        'answer': 'Visit the museum.',
        'sources': [
            {'title': 'Museum guide', 'page_start': 31, 'page_end': 31},
            {'title': 'Museum guide', 'page_start': 31, 'page_end': 31},
            {'title': 'Museum guide', 'page_start': 32, 'page_end': 32},
            {'title': 'Museum guide', 'page_start': 31, 'page_end': 31},
            {'title': 'Museum guide', 'page_start': 32, 'page_end': 32},
        ],
    }
    client = AsyncMock()
    client.post.return_value = response
    async_client.return_value.__aenter__.return_value = client
    messages: list[Message] = [
        {'role': 'user', 'content': 'First question'},
        {'role': 'assistant', 'content': 'First answer'},
        {'role': 'user', 'content': 'What should I visit?'},
    ]

    result = asyncio.run(
        HttpChatBackend('http://agent:8000/ask').generate_reply(messages)
    )

    assert (
        result == 'Visit the museum.\n\n**Sources**\n\nMuseum guide (pages 31 and 32)'
    )
    client.post.assert_awaited_once_with(
        'http://agent:8000/ask',
        json={'question': 'What should I visit?'},
    )
    response.raise_for_status.assert_called_once_with()
