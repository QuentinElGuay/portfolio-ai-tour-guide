import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from ai_tour_guide.agent.chat.models import Message, Role
from ai_tour_guide.agent.llm.clients import GenerationError, OpenAIClient, _parse_answer
from ai_tour_guide.agent.llm.factory import create_llm_client
from ai_tour_guide.agent.llm.fixture import BaguetteLLMClient, FixtureLLMClient
from ai_tour_guide.agent.llm.settings import (
    DEFAULT_BAGUETTE_LLM_DATASET_PATH,
    AgentsSettings,
    LLMProvider,
)
from ai_tour_guide.agent.responses import INSUFFICIENT_CONTEXT_ANSWER


def test_agent_settings_reads_generic_values_from_environment(
    monkeypatch,
) -> None:
    """Verify that agent settings reads generic values from environment."""
    monkeypatch.setenv('AGENT_LLM_API_KEY', 'test-token')
    monkeypatch.setenv('AGENT_LLM_MODEL', 'test-model')

    settings = AgentsSettings()

    assert settings.api_key.get_secret_value() == 'test-token'
    assert settings.model == 'test-model'


def test_openai_client_sends_messages_and_returns_structured_output() -> None:
    """Verify that openai client sends messages and returns structured output."""
    response = SimpleNamespace(
        output_text=(
            '{"answer": "A grounded answer.", "citations": [], "emotion": "happy"}'
        )
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
    assert result.emotion.value == 'happy'
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
    """Verify that default llm client is openai when openai is configured."""
    monkeypatch.setenv('AGENT_LLM_API_KEY', 'test-token')
    monkeypatch.setenv('AGENT_LLM_MODEL', 'test-model')

    client = create_llm_client(AgentsSettings())

    assert isinstance(client, OpenAIClient)
    assert client.model == 'test-model'


def test_llm_client_requires_api_key() -> None:
    """Verify that llm client requires api key."""
    settings = AgentsSettings(
        api_key=SecretStr(' '),
        model='test-model',
    )

    with pytest.raises(ValueError, match='API key must be provided'):
        create_llm_client(settings)


def test_fixture_client_returns_a_golden_answer_with_context_derived_citation(
    tmp_path,
) -> None:
    """Verify that fixture answers cite the matching context's first page."""
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
    """Verify that unsupported fixture questions return the fallback response."""
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
    """Verify that fixture answers require their expected source section."""
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
    """Verify that the deterministic fixture provider can run without an API key."""
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


def test_demo_provider_returns_a_friendly_supported_question(tmp_path) -> None:
    """Verify that the demo provider suggests a question outside its fixture."""
    dataset_path = tmp_path / 'golden.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'id': 1,
                'category': 'Test',
                'question': 'What can I do in Brittany?',
                'expected': {
                    'answerable': True,
                    'reference_answer': 'Visit the coast.',
                    'relevant_source': {
                        'source_url': 'https://example.test/guide',
                        'version': None,
                        'section_path': ['Guide', 'Activities'],
                    },
                },
            }
        )
        + '\n',
        encoding='utf-8',
    )

    result = asyncio.run(
        BaguetteLLMClient(dataset_path).answer_question(
            [{'role': Role.USER, 'content': 'User question:\nWhat is the weather?'}]
        )
    )

    assert 'demo backend with limited knowledge of Brittany' in result.answer
    assert 'What can I do in Brittany?' in result.answer
    assert result.citations == ()


def test_demo_provider_accepts_a_question_within_the_distance_margin(tmp_path) -> None:
    """Verify that a minor question variation resolves to a prepared answer."""
    dataset_path = tmp_path / 'golden.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'id': 1,
                'category': 'Test',
                'question': 'What can I do in Brittany?',
                'expected': {
                    'answerable': True,
                    'reference_answer': 'Visit the coast.',
                    'relevant_source': {
                        'source_url': 'https://example.test/guide',
                        'version': None,
                        'section_path': ['Guide', 'Activities'],
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
                'Pages: 4\nSection: Guide > Activities > Outdoor\n\n'
                'Context\n\nUser question:\nWhat can I do in Brittany'
            ),
        }
    ]

    result = asyncio.run(BaguetteLLMClient(dataset_path).answer_question(messages))

    assert result.answer == 'Visit the coast.'
    assert result.citations[0].page_start == 4


def test_demo_provider_suggests_a_close_question_with_did_you_mean(tmp_path) -> None:
    """Verify that a somewhat similar question gets a targeted suggestion."""
    dataset_path = tmp_path / 'golden.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'id': 1,
                'category': 'Test',
                'question': 'What can I do in Brittany?',
                'expected': {
                    'answerable': True,
                    'reference_answer': 'Visit the coast.',
                },
            }
        )
        + '\n',
        encoding='utf-8',
    )

    result = asyncio.run(
        BaguetteLLMClient(dataset_path).answer_question(
            [
                {
                    'role': Role.USER,
                    'content': 'User question:\nWhat activities can I do in Brittany?',
                }
            ]
        )
    )

    assert 'do not have a prepared answer' in result.answer
    assert 'Did you mean: “What can I do in Brittany?”' in result.answer
    assert result.citations == ()


def test_demo_provider_uses_the_bundled_dataset_without_an_api_key(tmp_path) -> None:
    """Verify that the no-cost demo ignores fixture-only configuration."""
    fixture_dataset_path = tmp_path / 'fixture-dataset.jsonl'
    client = create_llm_client(
        AgentsSettings(
            llm_provider=LLMProvider.BAGUETTE_LLM,
            model='mini-croissant-1.0',
            fixture_dataset_path=fixture_dataset_path,
        )
    )

    assert isinstance(client, BaguetteLLMClient)
    assert client.dataset_path == DEFAULT_BAGUETTE_LLM_DATASET_PATH


@pytest.mark.parametrize(
    'payload',
    [
        {},
        {'answer': '', 'citations': []},
        {'answer': 'Answer', 'citations': {}},
        {
            'answer': 'Answer',
            'citations': [
                {
                    'source_url': '',
                    'version': None,
                    'page_start': None,
                    'page_end': None,
                }
            ],
        },
        {
            'answer': 'Answer',
            'citations': [
                {
                    'source_url': 'https://example.test',
                    'version': None,
                    'page_start': True,
                    'page_end': None,
                }
            ],
        },
    ],
)
def test_parse_answer_rejects_invalid_structured_provider_payloads(
    payload: object,
) -> None:
    """Verify that malformed provider payloads cannot enter the citation pipeline."""
    with pytest.raises((TypeError, ValueError, KeyError)):
        _parse_answer(payload)


def test_openai_client_wraps_an_empty_structured_response() -> None:
    """Verify that empty provider output becomes a recoverable generation error."""
    client = MagicMock()
    client.responses.create = AsyncMock(return_value=SimpleNamespace(output_text='  '))
    settings = AgentsSettings(api_key=SecretStr('token'), model='model')

    with pytest.raises(GenerationError, match='empty response'):
        asyncio.run(OpenAIClient(settings, client=client).answer_question([]))
