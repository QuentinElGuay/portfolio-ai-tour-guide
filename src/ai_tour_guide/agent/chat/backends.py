import os
from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import uuid4

import httpx

from ai_tour_guide.agent.chat.models import Emotion, Message
from ai_tour_guide.agent.chat.navigation import (
    DESTINATION_CATALOG_QUESTION,
    MAIN_MENU,
    OPTIONS,
    normalize_option_id,
    question_for_option_id,
)
from ai_tour_guide.agent.identity import (  # noqa: F401
    IDENTITY_ANSWERS,
    TELL_ME_ABOUT_YOU_QUESTION,
)
from ai_tour_guide.agent.responses import NO_BACKEND_AVAILABLE_ANSWER

SUPPORTED_ASK_RESPONSE_SCHEMA_VERSION = 1
STARTER_QUESTIONS = tuple(OPTIONS[option_id].question for option_id in MAIN_MENU)
DEMO_STARTER_ANSWERS = {
    **IDENTITY_ANSWERS,
    DESTINATION_CATALOG_QUESTION: (
        'This demo covers a handful of questions about the beautiful region of Brittany.'
    ),
}


def create_backend() -> ChatBackend:
    api_url = os.getenv('CHAT_API_URL')
    if api_url:
        return HttpChatBackend(api_url=api_url)
    return DemoBackend()


class ChatBackend(ABC):
    """Backend contract with shared validation for API-shaped responses."""

    @abstractmethod
    async def ask(
        self, messages: Sequence[Message], *, option_id: str | None = None
    ) -> dict[str, object]:
        """Return a validated answer payload."""

    @abstractmethod
    async def submit_feedback(
        self, request_id: str, helpful: bool, comment: str | None = None
    ) -> None:
        """Submit answer feedback to the configured backend."""

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
        try:
            payload['emotion'] = Emotion(payload.get('emotion', Emotion.NEUTRAL)).value
        except ValueError as exc:
            raise ValueError('emotion must be one of the supported values') from exc
        return payload


class DemoBackend(ChatBackend):
    """Development fallback with the same payload contract as the API."""

    async def ask(
        self, messages: Sequence[Message], *, option_id: str | None = None
    ) -> dict[str, object]:
        question = next(
            (
                message['content']
                for message in reversed(messages)
                if message['role'] == 'user'
            ),
            '',
        )
        if option_id is not None:
            question = question_for_option_id(option_id) or question
        return self.validate_response(
            {
                'schema_version': SUPPORTED_ASK_RESPONSE_SCHEMA_VERSION,
                'answer': DEMO_STARTER_ANSWERS.get(
                    question, NO_BACKEND_AVAILABLE_ANSWER
                ),
                'sources': [],
                'emotion': Emotion.NEUTRAL.value,
            }
        )

    async def submit_feedback(
        self, request_id: str, helpful: bool, comment: str | None = None
    ) -> None:
        """Provide the feedback seam without performing any action."""
        del request_id, helpful, comment


class HttpChatBackend(ChatBackend):
    def __init__(self, api_url: str, timeout_seconds: float = 60.0) -> None:
        self.api_url = api_url
        self.timeout = httpx.Timeout(timeout_seconds)
        self.session_id = str(uuid4())

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

    async def ask(
        self, messages: Sequence[Message], *, option_id: str | None = None
    ) -> dict[str, object]:
        question = next(
            (
                message['content']
                for message in reversed(messages)
                if message['role'] == 'user'
            ),
            '',
        )
        selected_option_id = normalize_option_id(option_id)
        if selected_option_id is not None:
            question = question_for_option_id(selected_option_id) or question
        if not question.strip():
            raise RuntimeError('The conversation does not contain a user question.')
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url,
                    json={
                        'question': question,
                        'option_id': selected_option_id,
                        'session_id': self.session_id,
                    },
                )
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

    async def submit_feedback(
        self, request_id: str, helpful: bool, comment: str | None = None
    ) -> None:
        """Forward feedback to the agent API endpoint."""
        feedback_url = f'{self.api_url.rsplit("/", 1)[0]}/feedback'
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    feedback_url,
                    json={
                        'request_id': request_id,
                        'helpful': helpful,
                        'comment': comment,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f'Unable to store feedback: agent returned HTTP {exc.response.status_code}.'
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f'Unable to store feedback: {exc}') from exc
