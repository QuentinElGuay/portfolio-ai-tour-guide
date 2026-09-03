import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from ai_tour_guide.app.agent.demo_questions import (
    DEFAULT_DEMO_DATASET_PATH,
    DEMO_LIMITATION_MESSAGE,
)
from ai_tour_guide.app.agent.llm.clients import (
    GeminiClient,
    GenerationError,
    OpenAIClient,
    _parse_answer,
)
from ai_tour_guide.app.agent.llm.clients.demo import DemoLLMClient
from ai_tour_guide.app.agent.llm.factory import create_llm_client
from ai_tour_guide.app.agent.llm.retry import retry_provider_call
from ai_tour_guide.app.agent.llm.settings import (
    AgentsSettings,
    LLMProvider,
)
from ai_tour_guide.app.chat.models import Message, Role


def test_agent_settings_reads_generic_values_from_environment(
    monkeypatch,
) -> None:
    """Verify that agent settings reads generic values from environment."""
    monkeypatch.setenv('AGENT_LLM_API_KEY', 'test-token')
    monkeypatch.setenv('AGENT_LLM_MODEL', 'test-model')

    settings = AgentsSettings()

    assert settings.api_key.get_secret_value() == 'test-token'
    assert settings.model == 'test-model'


def test_agent_settings_uses_demo_question_distance_defaults() -> None:
    """Verify that demo question matching thresholds have the documented defaults."""
    settings = AgentsSettings(model='test-model')

    assert settings.close_question_distance == 0.25
    assert settings.similar_question_distance == 0.50


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


def test_gemini_client_sends_messages_and_returns_structured_output() -> None:
    """Verify that Gemini returns the shared structured answer contract."""
    response = SimpleNamespace(
        text='{"answer": "A grounded answer.", "citations": [], "emotion": "happy"}',
        usage_metadata=None,
    )
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=response)
    settings = AgentsSettings(
        api_key=SecretStr('test-token'),
        model='gemini-test-model',
    )

    result = asyncio.run(
        GeminiClient(settings, client=client).answer_question(
            [
                {'role': Role.SYSTEM, 'content': 'Use the context.'},
                {'role': Role.USER, 'content': 'What should I visit?'},
            ]
        )
    )

    assert result.answer == 'A grounded answer.'
    assert result.emotion.value == 'happy'
    await_call = client.aio.models.generate_content.await_args
    assert await_call is not None
    request = await_call.kwargs
    assert request['model'] == 'gemini-test-model'
    assert request['config'].response_mime_type == 'application/json'
    assert request['config'].system_instruction == 'Use the context.'
    citation_schema = request['config'].response_schema['properties']['citations']
    citation_properties = citation_schema['items']['properties']
    assert citation_properties['version'] == {
        'anyOf': [{'type': 'STRING'}, {'type': 'NULL'}]
    }
    assert citation_properties['page_start'] == {
        'anyOf': [{'type': 'INTEGER'}, {'type': 'NULL'}]
    }
    assert citation_properties['page_end'] == {
        'anyOf': [{'type': 'INTEGER'}, {'type': 'NULL'}]
    }


def test_gemini_client_extracts_search_tool_calls() -> None:
    """Verify that Gemini tool-call arguments become a search query."""
    function_call = SimpleNamespace(
        name='search_tourism_knowledge_base',
        args={'query': 'best places in Brittany'},
    )
    response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(function_call=function_call)]
                )
            )
        ]
    )
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=response)
    settings = AgentsSettings(
        api_key=SecretStr('test-token'),
        model='gemini-test-model',
    )

    result = asyncio.run(
        GeminiClient(settings, client=client).choose_search_query(
            'Where should I go?', previous_queries=(), has_context=False
        )
    )

    assert result == 'best places in Brittany'
    await_call = client.aio.models.generate_content.await_args
    assert await_call is not None
    request = await_call.kwargs
    parameters = request['config'].tools[0].function_declarations[0].parameters
    assert 'additionalProperties' not in parameters


def test_default_llm_client_is_openai_when_openai_is_configured(monkeypatch) -> None:
    """Verify that default llm client is openai when openai is configured."""
    monkeypatch.setenv('AGENT_LLM_API_KEY', 'test-token')
    monkeypatch.setenv('AGENT_LLM_MODEL', 'test-model')

    client = create_llm_client(AgentsSettings())

    assert isinstance(client, OpenAIClient)
    assert client.model == 'test-model'


def test_gemini_llm_client_is_selected_when_gemini_is_configured() -> None:
    """Verify that the factory selects Gemini for the configured provider."""
    client = create_llm_client(
        AgentsSettings(
            llm_provider=LLMProvider.GEMINI,
            api_key=SecretStr('test-token'),
            model='gemini-test-model',
        )
    )

    assert isinstance(client, GeminiClient)
    assert client.model == 'gemini-test-model'


def test_llm_client_requires_api_key() -> None:
    """Verify that llm client requires api key."""
    settings = AgentsSettings(
        api_key=SecretStr(' '),
        model='test-model',
    )

    with pytest.raises(ValueError, match='API key must be provided'):
        create_llm_client(settings)


def test_demo_client_returns_an_answer_with_context_derived_citation(
    tmp_path,
) -> None:
    """Verify that demo answers cite the matching context's first page."""
    dataset_path = tmp_path / 'demo.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'question': 'Where?',
                'answer': 'There.',
                'source': {
                    'source_url': 'https://example.test/guide',
                    'version': None,
                    'section_path': ['Guide', 'Places'],
                    'pages': [],
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

    result = asyncio.run(DemoLLMClient(dataset_path).answer_question(messages))

    assert result.answer == 'There.'
    assert result.citations[0].page_start == 4
    assert result.citations[0].page_end == 4


def test_demo_client_uses_fallback_for_an_unprepared_question(tmp_path) -> None:
    """Verify that an unprepared demo question returns the fallback response."""
    dataset_path = tmp_path / 'demo.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'question': 'Unsupported?',
                'answer': None,
                'source': None,
            }
        )
        + '\n',
        encoding='utf-8',
    )
    dataset_path.write_text(
        dataset_path.read_text(encoding='utf-8')
        + json.dumps(
            {
                'question': 'A prepared question?',
                'answer': 'A prepared answer.',
                'source': None,
            }
        )
        + '\n',
        encoding='utf-8',
    )

    result = asyncio.run(
        DemoLLMClient(dataset_path).answer_question(
            [{'role': Role.USER, 'content': 'User question:\nUnsupported?'}]
        )
    )

    assert result.answer.startswith(DEMO_LIMITATION_MESSAGE)
    assert result.citations == ()


def test_demo_client_uses_the_shared_notice_without_retrieved_evidence() -> None:
    """Verify that the no-evidence path preserves the demo disclosure and suggestion."""
    result = asyncio.run(
        DemoLLMClient().answer_without_context('Where should I eat crepes?')
    )

    assert result.answer.startswith(DEMO_LIMITATION_MESSAGE)
    assert '\n\nTry asking: “' in result.answer
    assert result.citations == ()


def test_demo_client_answers_a_prepared_question_without_retrieved_evidence() -> None:
    """Verify that demo mode remains useful before the knowledge base is ingested."""
    result = asyncio.run(
        DemoLLMClient().answer_without_context('What is kouign-amann?')
    )

    assert result.answer == (
        'Kouign-amann is a rich, buttery Breton pastry known for its caramelised '
        'sugar crust.'
    )
    assert result.citations == ()


def test_demo_client_falls_back_when_prepared_evidence_is_not_retrieved(
    tmp_path,
) -> None:
    """Verify that prepared answers are not returned without matching context."""
    dataset_path = tmp_path / 'demo.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'question': 'Where?',
                'answer': 'There.',
                'source': {
                    'source_url': 'https://example.test/guide',
                    'version': None,
                    'section_path': ['Guide', 'Places'],
                    'pages': [],
                },
            }
        )
        + '\n',
        encoding='utf-8',
    )

    result = asyncio.run(
        DemoLLMClient(dataset_path).answer_question(
            [{'role': Role.USER, 'content': 'User question:\nWhere?'}]
        )
    )

    assert result.answer.startswith(DEMO_LIMITATION_MESSAGE)


def test_demo_provider_does_not_require_an_api_key(tmp_path) -> None:
    """Verify that the deterministic demo provider can run without an API key."""
    dataset_path = tmp_path / 'demo.jsonl'
    dataset_path.write_text('', encoding='utf-8')

    client = create_llm_client(
        AgentsSettings(
            llm_provider=LLMProvider.BAGUETTE_LLM,
            model='demo',
            demo_dataset_path=dataset_path,
        )
    )

    assert isinstance(client, DemoLLMClient)


def test_demo_provider_returns_a_friendly_supported_question(tmp_path) -> None:
    """Verify that the demo provider suggests a prepared question."""
    dataset_path = tmp_path / 'demo.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'question': 'What can I do in Brittany?',
                'answer': 'Visit the coast.',
                'source': {
                    'source_url': 'https://example.test/guide',
                    'version': None,
                    'section_path': ['Guide', 'Activities'],
                    'pages': [],
                },
            }
        )
        + '\n',
        encoding='utf-8',
    )

    result = asyncio.run(
        DemoLLMClient(dataset_path).answer_question(
            [{'role': Role.USER, 'content': 'User question:\nWhat is the weather?'}]
        )
    )

    assert result.answer.startswith(DEMO_LIMITATION_MESSAGE)
    assert 'What can I do in Brittany?' in result.answer
    assert result.citations == ()


def test_demo_provider_accepts_a_question_within_the_distance_margin(tmp_path) -> None:
    """Verify that a minor question variation resolves to a prepared answer."""
    dataset_path = tmp_path / 'demo.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'question': 'What can I do in Brittany?',
                'answer': 'Visit the coast.',
                'source': {
                    'source_url': 'https://example.test/guide',
                    'version': None,
                    'section_path': ['Guide', 'Activities'],
                    'pages': [],
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

    result = asyncio.run(DemoLLMClient(dataset_path).answer_question(messages))

    assert result.answer == 'Visit the coast.'
    assert result.citations[0].page_start == 4


def test_demo_provider_suggests_a_close_question_with_did_you_mean(tmp_path) -> None:
    """Verify that a somewhat similar question gets a targeted suggestion."""
    dataset_path = tmp_path / 'demo.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'question': 'What can I do in Brittany?',
                'answer': 'Visit the coast.',
                'source': None,
            }
        )
        + '\n',
        encoding='utf-8',
    )

    result = asyncio.run(
        DemoLLMClient(dataset_path).answer_question(
            [
                {
                    'role': Role.USER,
                    'content': 'User question:\nWhat activities can I do in Brittany?',
                }
            ]
        )
    )

    assert result.answer.startswith(DEMO_LIMITATION_MESSAGE)
    assert 'Did you mean: “What can I do in Brittany?”' in result.answer
    assert result.citations == ()


def test_demo_provider_uses_the_bundled_dataset_without_an_api_key(tmp_path) -> None:
    """Verify that the no-cost demo uses its bundled dataset by default."""
    client = create_llm_client(
        AgentsSettings(
            llm_provider=LLMProvider.BAGUETTE_LLM,
            model='mini-croissant-1.0',
        )
    )

    assert isinstance(client, DemoLLMClient)
    assert client.dataset_path == DEFAULT_DEMO_DATASET_PATH


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


def test_retry_provider_call_retries_transient_failures(monkeypatch) -> None:
    """Verify that a transient provider failure is retried with backoff."""
    attempts = 0
    sleeps: list[float] = []

    class TemporaryProviderError(RuntimeError):
        status_code = 503

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TemporaryProviderError()
        return 'ok'

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr('ai_tour_guide.app.agent.llm.retry.asyncio.sleep', fake_sleep)

    assert asyncio.run(retry_provider_call(operation)) == 'ok'
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


def test_retry_provider_call_does_not_retry_permanent_failures() -> None:
    """Verify that invalid provider requests fail immediately."""
    attempts = 0

    class PermanentProviderError(RuntimeError):
        status_code = 400

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise PermanentProviderError()

    with pytest.raises(PermanentProviderError):
        asyncio.run(retry_provider_call(operation))
    assert attempts == 1
