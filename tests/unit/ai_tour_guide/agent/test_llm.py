import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import SecretStr

from ai_tour_guide.agent.chat.backends import LocalBackend, create_backend
from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.llm.client import OpenAIClient
from ai_tour_guide.agent.llm.settings import OpenAISettings


def test_openai_settings_reads_the_agent_api_key_from_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv('AGENT_OPENAI_API_KEY', 'test-token')
    monkeypatch.setenv('AGENT_OPENAI_MODEL', 'test-model')

    settings = OpenAISettings()

    assert settings.api_key.get_secret_value() == 'test-token'
    assert settings.model == 'test-model'


def test_openai_client_sends_messages_and_returns_output_text() -> None:
    response = SimpleNamespace(output_text='A grounded answer.')
    client = MagicMock()
    client.responses.create = AsyncMock(return_value=response)
    settings = OpenAISettings(
        api_key=SecretStr('test-token'),
        model='test-model',
    )
    messages: list[Message] = [
        {'role': 'system', 'content': 'Use the context.'},
        {'role': 'user', 'content': 'What should I visit?'},
    ]

    result = asyncio.run(OpenAIClient(settings, client=client).generate(messages))

    assert result == 'A grounded answer.'
    client.responses.create.assert_awaited_once_with(
        model='test-model',
        input=[
            {'role': 'system', 'content': 'Use the context.'},
            {'role': 'user', 'content': 'What should I visit?'},
        ],
    )


@patch('ai_tour_guide.agent.chat.backends.LocalBackend')
def test_create_backend_prefers_local_backend_when_openai_is_configured(
    local_backend: MagicMock,
    monkeypatch,
) -> None:
    monkeypatch.setenv('AGENT_OPENAI_API_KEY', 'test-token')
    monkeypatch.setenv('CHAT_API_URL', 'http://localhost:8000/chat')

    result = create_backend()

    assert result is local_backend.return_value
    local_backend.assert_called_once()
    settings = local_backend.call_args.kwargs['settings']
    assert settings.api_key.get_secret_value() == 'test-token'


def test_local_backend_delegates_to_the_llm_client() -> None:
    client = MagicMock()
    client.generate = AsyncMock(return_value='A direct answer.')
    messages: list[Message] = [
        {'role': 'user', 'content': 'What should I visit?'},
    ]

    result = asyncio.run(LocalBackend(client=client).generate_reply(messages))

    assert result == 'A direct answer.'
    client.generate.assert_awaited_once_with(messages)
