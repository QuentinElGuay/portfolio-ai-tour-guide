"""OpenAI implementation of the language-model client."""

import json
from collections.abc import Sequence

from openai import APIError, AsyncOpenAI
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall

from ai_tour_guide.app.agent.llm.clients import GenerationError
from ai_tour_guide.app.agent.llm.rate_limit import AsyncRateLimiter
from ai_tour_guide.app.agent.llm.settings import AgentsSettings
from ai_tour_guide.app.agent.rag.models import GeneratedAnswer, LLMCitation
from ai_tour_guide.app.agent.rag.tools import TOURISM_SEARCH_TOOL
from ai_tour_guide.app.chat.models import Emotion, Message, Role


def create_openai_client(settings: AgentsSettings) -> AsyncOpenAI:
    """Create the shared low-level OpenAI client from agent settings."""
    return AsyncOpenAI(api_key=settings.api_key.get_secret_value())


class OpenAIClient:
    """Generate responses directly through the OpenAI Responses API."""

    def __init__(
        self,
        settings: AgentsSettings,
        *,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.model = settings.model
        self._rate_limiter = AsyncRateLimiter(settings.requests_per_second)
        self._client = client or create_openai_client(settings)

    async def answer_question(self, messages: Sequence[Message]) -> GeneratedAnswer:
        """Generate one assistant response for the supplied messages."""
        await self._rate_limiter.acquire()
        try:
            response = await self._client.responses.create(
                model=self.model,
                input=[
                    {
                        'role': (
                            message['role'].value
                            if isinstance(message['role'], Role)
                            else message['role']
                        ),
                        'content': message['content'],
                    }
                    for message in messages
                ],
                text={
                    'format': {
                        'type': 'json_schema',
                        'name': 'generated_answer',
                        'strict': True,
                        'schema': {
                            'type': 'object',
                            'properties': {
                                'answer': {'type': 'string'},
                                'citations': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'source_url': {'type': 'string'},
                                            'version': {'type': ['string', 'null']},
                                            'page_start': {'type': ['integer', 'null']},
                                            'page_end': {'type': ['integer', 'null']},
                                        },
                                        'required': [
                                            'source_url',
                                            'version',
                                            'page_start',
                                            'page_end',
                                        ],
                                        'additionalProperties': False,
                                    },
                                },
                                'emotion': {
                                    'type': 'string',
                                    'enum': [emotion.value for emotion in Emotion],
                                },
                            },
                            'required': ['answer', 'citations', 'emotion'],
                            'additionalProperties': False,
                        },
                    },
                },
            )
        except APIError as exc:
            raise GenerationError(f'OpenAI request failed: {exc}') from exc

        content = response.output_text
        if not isinstance(content, str) or not content.strip():
            raise GenerationError('OpenAI returned an empty response.')
        try:
            answer, citations, emotion = _parse_answer(json.loads(content))
        except (TypeError, ValueError, KeyError) as exc:
            raise GenerationError(
                'OpenAI returned malformed structured output.'
            ) from exc
        usage = getattr(response, 'usage', None)
        usage_payload = usage.model_dump() if usage is not None else None
        return GeneratedAnswer(
            answer=answer,
            citations=citations,
            emotion=emotion,
            llm_metadata={
                'provider': 'openai',
                'model': self.model,
                'response_id': getattr(response, 'id', None),
                'status': getattr(response, 'status', None),
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
        """Ask the model whether to call the sole knowledge-base search tool."""
        await self._rate_limiter.acquire()
        try:
            response = await self._client.responses.create(
                model=self.model,
                input=[
                    {
                        'role': 'system',
                        'content': (
                            'You are a source-grounded travel assistant. Call '
                            f'`{TOURISM_SEARCH_TOOL.name}` for every factual tourism question. '
                            'Do not call it only for conversational or meta questions about '
                            'the assistant and its capabilities. Never answer tourism facts '
                            'from model knowledge. If a previous search was insufficient, you '
                            'may call the tool once more with a reformulated query. '
                            f'Previous queries: {list(previous_queries)!r}. '
                            f'Retrieved context available: {has_context}.'
                        ),
                    },
                    {'role': 'user', 'content': question},
                ],
                tools=[
                    {
                        'type': 'function',
                        'name': TOURISM_SEARCH_TOOL.name,
                        'description': TOURISM_SEARCH_TOOL.description,
                        'parameters': TOURISM_SEARCH_TOOL.input_schema,
                        'strict': True,
                    }
                ],
                parallel_tool_calls=False,
            )
        except APIError as exc:
            raise GenerationError(f'OpenAI request failed: {exc}') from exc
        for item in response.output:
            if not isinstance(item, ResponseFunctionToolCall):
                continue
            if item.name != TOURISM_SEARCH_TOOL.name:
                continue
            try:
                query = json.loads(item.arguments)['query']
            except (KeyError, TypeError, ValueError) as exc:
                raise GenerationError(
                    'OpenAI returned an invalid search tool call.'
                ) from exc
            if isinstance(query, str) and query.strip():
                return query.strip()
            raise GenerationError('OpenAI returned an empty search query.')
        return None


def _parse_answer(
    payload: object,
) -> tuple[str, tuple[LLMCitation, ...], Emotion]:
    if not isinstance(payload, dict):
        raise TypeError('answer must be an object')

    answer = payload.get('answer')
    citations = payload.get('citations')
    emotion = payload.get('emotion', Emotion.NEUTRAL)
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError('answer must be a non-empty string')
    if not isinstance(citations, list):
        raise TypeError('citations must be a list')
    try:
        parsed_emotion = Emotion(emotion)
    except ValueError as exc:
        raise ValueError('emotion must be one of the supported values') from exc

    parsed_citations: list[LLMCitation] = []
    for citation in citations:
        if not isinstance(citation, dict):
            raise TypeError('citation must be an object')
        source_url = citation.get('source_url')
        version = citation.get('version')
        page_start = citation.get('page_start')
        page_end = citation.get('page_end')
        if not isinstance(source_url, str) or not source_url.strip():
            raise ValueError('citation source_url must be a non-empty string')
        if version is not None and not isinstance(version, str):
            raise TypeError('citation version must be a string or null')
        if page_start is not None and (
            not isinstance(page_start, int) or isinstance(page_start, bool)
        ):
            raise TypeError('citation page_start must be an integer or null')
        if page_end is not None and (
            not isinstance(page_end, int) or isinstance(page_end, bool)
        ):
            raise TypeError('citation page_end must be an integer or null')
        parsed_citations.append(LLMCitation(source_url, version, page_start, page_end))

    return answer, tuple(parsed_citations), parsed_emotion


__all__ = [
    'OpenAIClient',
    'create_openai_client',
]
