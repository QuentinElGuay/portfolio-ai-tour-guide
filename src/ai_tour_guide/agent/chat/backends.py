import os
from abc import ABC, abstractmethod
from collections.abc import Sequence

import httpx

from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.responses import NO_BACKEND_AVAILABLE_ANSWER

SUPPORTED_ASK_RESPONSE_SCHEMA_VERSION = 1


def create_backend() -> ChatBackend:
    api_url = os.getenv('CHAT_API_URL')
    if api_url:
        return HttpChatBackend(api_url=api_url)
    return DemoBackend()


class ChatBackend(ABC):
    """Backend contract with shared validation for API-shaped responses."""

    @abstractmethod
    async def ask(self, messages: Sequence[Message]) -> dict[str, object]:
        """Return a validated answer payload."""

    @abstractmethod
    async def submit_feedback(self, request_id: str, helpful: bool) -> None:
        """Accept answer feedback without persisting it yet."""

    @staticmethod
    def validate_response(payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise TypeError('response must be an object')
        if payload.get('schema_version') != SUPPORTED_ASK_RESPONSE_SCHEMA_VERSION:
            raise ValueError('unsupported schema version')

        answer = payload.get('answer')
        sources = payload.get('sources')
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError('answer must be a non-empty string')
        if not isinstance(sources, list):
            raise TypeError('sources must be a list')
        return payload


class DemoBackend(ChatBackend):
    """Development fallback with the same payload contract as the API."""

    async def ask(self, messages: Sequence[Message]) -> dict[str, object]:
        return self.validate_response(
            {
                'schema_version': SUPPORTED_ASK_RESPONSE_SCHEMA_VERSION,
                'answer': NO_BACKEND_AVAILABLE_ANSWER,
                'sources': [],
            }
        )

    async def submit_feedback(self, request_id: str, helpful: bool) -> None:
        """Provide the feedback seam without performing any action."""
        del request_id, helpful


class HttpChatBackend(ChatBackend):
    def __init__(self, api_url: str, timeout_seconds: float = 60.0) -> None:
        self.api_url = api_url
        self.timeout = httpx.Timeout(timeout_seconds)

    async def check_ready(self) -> None:
        """Verify that the API and its configured knowledge base are ready."""
        health_url = f'{self.api_url.rsplit("/", 1)[0]}/health'
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(health_url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ''
            try:
                payload = exc.response.json()
                detail = payload.get('detail', '') if isinstance(payload, dict) else ''
            except ValueError:
                pass
            message = f' Chat API health check failed: {detail}' if detail else ''
            raise RuntimeError(f'The chat API is not ready.{message}') from exc
        except httpx.HTTPError as exc:
            raise RuntimeError('Unable to reach the chat API health check.') from exc

    async def ask(self, messages: Sequence[Message]) -> dict[str, object]:
        question = next(
            (
                message['content']
                for message in reversed(messages)
                if message['role'] == 'user'
            ),
            '',
        )
        if not question.strip():
            raise RuntimeError('The conversation does not contain a user question.')
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.api_url, json={'question': question})
                response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError('Unable to connect to the chat API.') from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f'The chat API returned HTTP {exc.response.status_code}.'
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f'Chat API request failed: {exc}') from exc
        try:
            payload = self.validate_response(response.json())
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "Invalid API response. Expected {'answer': '...', 'sources': [...]}."
            ) from exc

        return payload

    async def submit_feedback(self, request_id: str, helpful: bool) -> None:
        """Provide the feedback seam until a feedback endpoint exists."""
        del request_id, helpful
