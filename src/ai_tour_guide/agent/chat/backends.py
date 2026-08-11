from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Protocol

import httpx
from pydantic import ValidationError

from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.llm.client import OpenAIClient
from ai_tour_guide.agent.llm.settings import OpenAISettings


# Backend Factory
def create_backend() -> ChatBackend:
    """Create the configured chat backend for agent applications."""
    try:
        openai_settings = OpenAISettings()
    except ValidationError:
        openai_settings = None

    if openai_settings is not None:
        return LocalBackend(settings=openai_settings)

    api_url = os.getenv('CHAT_API_URL')

    if api_url:
        return HttpChatBackend(api_url=api_url)

    return DemoBackend()


class ChatBackend(Protocol):
    async def generate(self, messages: Sequence[Message]) -> str:
        """Return an assistant response for the complete conversation."""


class LocalBackend:
    """Generate responses directly without a separate application server."""

    def __init__(
        self,
        client: OpenAIClient | None = None,
        *,
        settings: OpenAISettings | None = None,
    ) -> None:
        self.client = client or OpenAIClient(settings)

    async def generate(self, messages: Sequence[Message]) -> str:
        """Delegate generation to the configured direct LLM client."""
        return await self.client.generate(messages)


class DemoBackend:
    """Local backend that makes the UI runnable without an LLM provider."""

    async def generate(self, messages: Sequence[Message]) -> str:
        latest = messages[-1]['content']

        return (
            'This is the local demo backend.\n\n'
            f'You said: **{latest}**\n\n'
            'Set `CHAT_API_URL` to connect this interface to your Python API.'
        )


class HttpChatBackend:
    """Adapter for a separate HTTP chat API."""

    def __init__(self, api_url: str, timeout_seconds: float = 60.0) -> None:
        self.api_url = api_url
        self.timeout = httpx.Timeout(timeout_seconds)

    async def generate(self, messages: Sequence[Message]) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url,
                    json={'messages': list(messages)},
                )
                response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                'Unable to connect to the chat API. '
                'Make sure the backend is running and CHAT_API_URL is correct.'
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise RuntimeError(
                f'The chat API returned HTTP {exc.response.status_code}: {detail}'
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f'Chat API request failed: {exc}') from exc

        try:
            payload = response.json()
            message = payload['message']
            content = message['content']
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(
                'Invalid API response. Expected '
                "{'message': {'role': 'assistant', 'content': '...'}}."
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError('The chat API returned an empty response.')

        return content
