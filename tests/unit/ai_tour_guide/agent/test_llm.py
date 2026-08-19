import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from ai_tour_guide.agent.chat.models import Message, Role
from ai_tour_guide.agent.llm.clients import OpenAIClient
from ai_tour_guide.agent.llm.factory import create_llm_client
from ai_tour_guide.agent.llm.settings import AgentsSettings


def test_agent_settings_reads_generic_values_from_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv('AGENT_LLM_API_KEY', 'test-token')
    monkeypatch.setenv('AGENT_LLM_MODEL', 'test-model')

    settings = AgentsSettings()

    assert settings.api_key.get_secret_value() == 'test-token'
    assert settings.model == 'test-model'


def test_openai_client_sends_messages_and_returns_structured_output() -> None:
    response = SimpleNamespace(
        output_text='{"answer": "A grounded answer.", "citations": []}'
    )
    client = MagicMock()
    client.responses.create = AsyncMock(return_value=response)
    settings = AgentsSettings(
        api_key=SecretStr('test-token'),
        model='test-model',
    )
    messages: list[Message] = [
        {'role': Role.SYSTEM, 'content': 'Use the context.'},
        {'role': Role.USER, 'content': 'What should I visit?'},
    ]

    result = asyncio.run(
        OpenAIClient(settings, client=client).answer_question(messages)
    )

    assert result.answer == 'A grounded answer.'
    await_args = client.responses.create.await_args
    assert await_args is not None
    request = await_args.kwargs
    assert request['model'] == 'test-model'
    assert request['input'] == [
        {'role': 'system', 'content': 'Use the context.'},
        {'role': 'user', 'content': 'What should I visit?'},
    ]
    assert request['text']['format']['type'] == 'json_schema'


def test_default_llm_client_is_openai_when_openai_is_configured(monkeypatch) -> None:
    monkeypatch.setenv('AGENT_LLM_API_KEY', 'test-token')
    monkeypatch.setenv('AGENT_LLM_MODEL', 'test-model')

    client = create_llm_client(AgentsSettings())

    assert isinstance(client, OpenAIClient)
    assert client.model == 'test-model'


def test_llm_client_requires_api_key() -> None:
    settings = AgentsSettings(
        api_key=SecretStr(' '),
        model='test-model',
    )

    with pytest.raises(ValueError, match='API key must be provided'):
        create_llm_client(settings)
