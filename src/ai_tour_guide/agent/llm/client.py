"""Direct OpenAI client implementing the agent chat backend protocol."""

from collections.abc import Sequence

from openai import APIError, AsyncOpenAI

from ai_tour_guide.agent.chat.models import Message, Role
from ai_tour_guide.agent.llm.interfaces import GenerationError
from ai_tour_guide.agent.llm.rate_limit import AsyncRateLimiter
from ai_tour_guide.agent.llm.settings import OpenAISettings
from ai_tour_guide.agent.rag.models import GeneratedAnswer, LLMCitation


class OpenAIClient:
    """Generate responses directly through the OpenAI Responses API."""

    def __init__(
        self,
        settings: OpenAISettings | None = None,
        *,
        client: AsyncOpenAI | None = None,
    ) -> None:
        selected_settings = settings or OpenAISettings()
        self.model = selected_settings.model
        self._rate_limiter = AsyncRateLimiter(selected_settings.requests_per_second)
        self._client = client or AsyncOpenAI(
            api_key=selected_settings.api_key.get_secret_value(),
        )

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
                            },
                            'required': ['answer', 'citations'],
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
            import json

            answer, citations = _parse_answer(json.loads(content))
        except (TypeError, ValueError, KeyError) as exc:
            raise GenerationError(
                'OpenAI returned malformed structured output.'
            ) from exc
        usage = getattr(response, 'usage', None)
        usage_payload = usage.model_dump() if usage is not None else None
        return GeneratedAnswer(
            answer=answer,
            citations=citations,
            llm_metadata={
                'provider': 'openai',
                'model': self.model,
                'response_id': getattr(response, 'id', None),
                'status': getattr(response, 'status', None),
                'usage': usage_payload,
            },
            raw_provider_response=response,
        )


def _parse_answer(payload: object) -> tuple[str, tuple[LLMCitation, ...]]:
    if not isinstance(payload, dict):
        raise TypeError('answer must be an object')

    answer = payload.get('answer')
    citations = payload.get('citations')
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError('answer must be a non-empty string')
    if not isinstance(citations, list):
        raise TypeError('citations must be a list')

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

    return answer, tuple(parsed_citations)


__all__ = ['OpenAIClient']
