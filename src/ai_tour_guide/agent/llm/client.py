"""Direct OpenAI client implementing the agent chat backend protocol."""

from collections.abc import Sequence

from openai import APIError, AsyncOpenAI

from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.llm.interfaces import GenerationError
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
        self._client = client or AsyncOpenAI(
            api_key=selected_settings.api_key.get_secret_value(),
        )

    async def answer_question(self, messages: Sequence[Message]) -> GeneratedAnswer:
        """Generate one assistant response for the supplied messages."""
        try:
            response = await self._client.responses.create(
                model=self.model,
                input=[
                    {'role': message['role'], 'content': message['content']}
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

            payload = json.loads(content)
            answer = payload['answer']
            citations = tuple(
                LLMCitation(**citation) for citation in payload['citations']
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise GenerationError(
                'OpenAI returned malformed structured output.'
            ) from exc
        if not isinstance(answer, str) or not answer.strip():
            raise GenerationError('OpenAI returned an empty structured answer.')
        usage = getattr(response, 'usage', None)
        usage_payload = (
            usage.model_dump()
            if hasattr(usage, 'model_dump')
            else str(usage)
            if usage is not None
            else None
        )
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


__all__ = ['OpenAIClient']
