"""Direct OpenAI client implementing the agent chat backend protocol."""

from collections.abc import Sequence

from openai import APIError, AsyncOpenAI

from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.llm.settings import OpenAISettings


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

    async def generate(self, messages: Sequence[Message]) -> str:
        """Generate one assistant response for the supplied messages."""
        try:
            response = await self._client.responses.create(
                model=self.model,
                input=[
                    {'role': message['role'], 'content': message['content']}
                    for message in messages
                ],
            )
        except APIError as exc:
            raise RuntimeError(f'OpenAI request failed: {exc}') from exc

        content = response.output_text
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError('OpenAI returned an empty response.')

        return content


__all__ = ['OpenAIClient']
