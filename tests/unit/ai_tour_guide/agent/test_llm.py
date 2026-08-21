import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from ai_tour_guide.agent.chat.models import Message, Role
from ai_tour_guide.agent.llm.clients import GenerationError, OpenAIClient
from ai_tour_guide.agent.llm.factory import create_llm_client
from ai_tour_guide.agent.llm.fixture import FixtureLLMClient
from ai_tour_guide.agent.llm.settings import AgentsSettings, LLMProvider
from ai_tour_guide.agent.responses import INSUFFICIENT_CONTEXT_ANSWER


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


def test_fixture_client_returns_a_golden_answer_with_context_derived_citation(
    tmp_path,
) -> None:
    dataset_path = tmp_path / 'golden.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'id': 1,
                'category': 'Test',
                'question': 'Where?',
                'expected': {
                    'answerable': True,
                    'reference_answer': 'There.',
                    'relevant_source': {
                        'source_url': 'https://example.test/guide',
                        'version': None,
                        'section_path': ['Guide', 'Places'],
                    },
                },
            }
        )
        + '\n',
        encoding='utf-8',
    )
    messages: list[Message] = [
        {
            'role': Role.USER,
            'content': (
                'Retrieved context:\n\nSource: Guide\n'
                'URL: https://example.test/guide\nVersion: null\n'
                'Pages: 4, 5\nSection: Guide > Places > Towns\n\n'
                'Context\n\nUser question:\nWhere?'
            ),
        }
    ]

    result = asyncio.run(FixtureLLMClient(dataset_path).answer_question(messages))

    assert result.answer == 'There.'
    assert result.citations[0].page_start == 4
    assert result.citations[0].page_end == 4


def test_fixture_client_refuses_an_unsupported_golden_question(tmp_path) -> None:
    dataset_path = tmp_path / 'golden.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'id': 1,
                'category': 'Test',
                'question': 'Unsupported?',
                'expected': {
                    'answerable': False,
                    'reference_answer': None,
                },
            }
        )
        + '\n',
        encoding='utf-8',
    )

    result = asyncio.run(
        FixtureLLMClient(dataset_path).answer_question(
            [{'role': Role.USER, 'content': 'User question:\nUnsupported?'}]
        )
    )

    assert result.answer == INSUFFICIENT_CONTEXT_ANSWER
    assert result.citations == ()


def test_fixture_client_fails_when_expected_evidence_is_not_retrieved(tmp_path) -> None:
    dataset_path = tmp_path / 'golden.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'id': 1,
                'category': 'Test',
                'question': 'Where?',
                'expected': {
                    'answerable': True,
                    'reference_answer': 'There.',
                    'relevant_source': {
                        'source_url': 'https://example.test/guide',
                        'version': None,
                        'section_path': ['Guide', 'Places'],
                    },
                },
            }
        )
        + '\n',
        encoding='utf-8',
    )

    with pytest.raises(GenerationError, match='Expected fixture evidence'):
        asyncio.run(
            FixtureLLMClient(dataset_path).answer_question(
                [{'role': Role.USER, 'content': 'User question:\nWhere?'}]
            )
        )


def test_fixture_provider_does_not_require_an_api_key(tmp_path) -> None:
    dataset_path = tmp_path / 'golden.jsonl'
    dataset_path.write_text('', encoding='utf-8')

    client = create_llm_client(
        AgentsSettings(
            llm_provider=LLMProvider.FIXTURE,
            model='fixture',
            fixture_dataset_path=dataset_path,
        )
    )

    assert isinstance(client, FixtureLLMClient)
