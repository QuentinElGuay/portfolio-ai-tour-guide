"""Google Gemini implementation of the language-model client."""

import json
from collections.abc import Sequence
from typing import cast

from google import genai
from google.genai import errors, types

from ai_tour_guide.app.chat.models import Emotion, Message, Role
from ai_tour_guide.app.llm.clients import GenerationError
from ai_tour_guide.app.llm.clients.openai import _parse_answer
from ai_tour_guide.app.llm.rate_limit import AsyncRateLimiter
from ai_tour_guide.app.llm.retry import retry_provider_call
from ai_tour_guide.app.llm.settings import AgentsSettings
from ai_tour_guide.app.services.rag.models import GeneratedAnswer, LLMCitation
from ai_tour_guide.app.services.rag.tools import TOURISM_SEARCH_TOOL


def create_gemini_client(settings: AgentsSettings) -> genai.Client:
    """Create the shared low-level Gemini client from agent settings."""
    return genai.Client(api_key=settings.api_key.get_secret_value())


class GeminiClient:
    """Generate responses through the Google Gemini API."""

    def __init__(
        self,
        settings: AgentsSettings,
        *,
        client: genai.Client | None = None,
    ) -> None:
        self.model = settings.model
        self._rate_limiter = AsyncRateLimiter(settings.requests_per_second)
        self._client = client or create_gemini_client(settings)

    async def answer_question(self, messages: Sequence[Message]) -> GeneratedAnswer:
        """Generate one structured assistant response."""
        await self._rate_limiter.acquire()
        try:
            response = await retry_provider_call(
                lambda: self._client.aio.models.generate_content(
                    model=self.model,
                    contents=cast(types.ContentListUnion, _contents(messages)),
                    config=types.GenerateContentConfig(
                        system_instruction=_system_instruction(messages),
                        response_mime_type='application/json',
                        response_schema={
                            'type': 'OBJECT',
                            'properties': {
                                'answer': {'type': 'STRING'},
                                'citations': {
                                    'type': 'ARRAY',
                                    'items': {
                                        'type': 'OBJECT',
                                        'properties': {
                                            'source_url': {'type': 'STRING'},
                                            'version': _gemini_nullable_schema(
                                                'STRING'
                                            ),
                                            'page_start': {
                                                **_gemini_nullable_schema('INTEGER'),
                                            },
                                            'page_end': {
                                                **_gemini_nullable_schema('INTEGER'),
                                            },
                                        },
                                        'required': [
                                            'source_url',
                                            'version',
                                            'page_start',
                                            'page_end',
                                        ],
                                    },
                                },
                                'emotion': {
                                    'type': 'STRING',
                                    'enum': [emotion.value for emotion in Emotion],
                                },
                            },
                            'required': ['answer', 'citations', 'emotion'],
                        },
                    ),
                )
            )
        except errors.APIError as exc:
            raise GenerationError(f'Gemini request failed: {exc}') from exc

        content = response.text
        if not isinstance(content, str) or not content.strip():
            raise GenerationError('Gemini returned an empty response.')
        try:
            answer, citations, emotion = _parse_answer_json(content)
        except (TypeError, ValueError, KeyError) as exc:
            raise GenerationError(
                'Gemini returned malformed structured output.'
            ) from exc
        usage = getattr(response, 'usage_metadata', None)
        usage_payload = usage.model_dump() if usage is not None else None
        return GeneratedAnswer(
            answer=answer,
            citations=citations,
            emotion=emotion,
            llm_metadata={
                'provider': 'gemini',
                'model': self.model,
                'response_id': getattr(response, 'response_id', None),
                'usage': usage_payload,
            },
            raw_provider_response=response,
        )

    async def choose_search_query(
        self,
        question: str,
        *,
        previous_queries: Sequence[str],
        has_context: bool,
    ) -> str | None:
        """Ask Gemini whether to call the sole knowledge-base search tool."""
        await self._rate_limiter.acquire()
        try:
            response = await retry_provider_call(
                lambda: self._client.aio.models.generate_content(
                    model=self.model,
                    contents=question,
                    config=types.GenerateContentConfig(
                        system_instruction=(
                            'You are a source-grounded travel assistant. Call '
                            f'`{TOURISM_SEARCH_TOOL.name}` for every factual tourism question. '
                            'Do not call it only for conversational or meta questions about '
                            'the assistant and its capabilities. Never answer tourism facts '
                            'from model knowledge. If a previous search was insufficient, you '
                            'may call the tool once more with a reformulated query. '
                            f'Previous queries: {list(previous_queries)!r}. '
                            f'Retrieved context available: {has_context}.'
                        ),
                        tools=[
                            types.Tool(
                                function_declarations=[
                                    types.FunctionDeclaration(
                                        name=TOURISM_SEARCH_TOOL.name,
                                        description=TOURISM_SEARCH_TOOL.description,
                                        parameters=cast(
                                            types.Schema,
                                            _gemini_tool_schema(
                                                TOURISM_SEARCH_TOOL.input_schema
                                            ),
                                        ),
                                    )
                                ]
                            )
                        ],
                        tool_config=types.ToolConfig(
                            function_calling_config=types.FunctionCallingConfig(
                                mode=types.FunctionCallingConfigMode.AUTO
                            )
                        ),
                    ),
                )
            )
        except errors.APIError as exc:
            raise GenerationError(f'Gemini request failed: {exc}') from exc

        for candidate in getattr(response, 'candidates', ()):
            content = getattr(candidate, 'content', None)
            for part in getattr(content, 'parts', ()):
                function_call = getattr(part, 'function_call', None)
                if function_call is None:
                    continue
                if function_call.name != TOURISM_SEARCH_TOOL.name:
                    continue
                args = function_call.args
                query = args.get('query') if isinstance(args, dict) else None
                if isinstance(query, str) and query.strip():
                    return query.strip()
                raise GenerationError('Gemini returned an empty search query.')
        return None


def _contents(messages: Sequence[Message]) -> list[types.Content]:
    """Convert provider-neutral messages to Gemini content objects."""
    return [
        types.Content(
            role=(
                message['role'].value
                if isinstance(message['role'], Role)
                else message['role']
            ),
            parts=[types.Part.from_text(text=message['content'])],
        )
        for message in messages
        if message['role'] is not Role.SYSTEM
    ]


def _system_instruction(messages: Sequence[Message]) -> str | None:
    """Collect system messages into Gemini's system instruction field."""
    instructions = [
        message['content'] for message in messages if message['role'] == Role.SYSTEM
    ]
    return '\n\n'.join(instructions) or None


def _parse_answer_json(
    content: str,
) -> tuple[str, tuple[LLMCitation, ...], Emotion]:
    """Parse Gemini's JSON text with the shared provider-neutral validator."""
    return _parse_answer(json.loads(content))


def _gemini_tool_schema(schema: dict[str, object]) -> dict[str, object]:
    """Adapt the shared JSON Schema to Gemini's supported schema fields.

    Gemini's function declaration schema does not accept the JSON Schema
    ``additionalProperties`` keyword, although it is useful to providers such
    as OpenAI for enforcing strict tool arguments.
    """
    return {
        key: value for key, value in schema.items() if key != 'additionalProperties'
    }


def _gemini_nullable_schema(type_name: str) -> dict[str, object]:
    """Build a Gemini schema for a value that may also be JSON null."""
    return {
        'anyOf': [
            {'type': type_name},
            {'type': 'NULL'},
        ]
    }


__all__ = ['GeminiClient', 'create_gemini_client']
