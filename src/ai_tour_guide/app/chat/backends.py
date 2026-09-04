import asyncio
import logging
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx

from ai_tour_guide.app.agent.demo_questions import DEMO_WELCOME_MESSAGE
from ai_tour_guide.app.agent.flow import (
    FLOW_QUESTIONS,
    FlowStep,
    flow_definition,
    transition_for,
)
from ai_tour_guide.app.agent.identity import IDENTITY_ANSWERS
from ai_tour_guide.app.agent.responses import NO_BACKEND_AVAILABLE_ANSWER
from ai_tour_guide.app.chat.models import (
    FREE_TEXT_INPUT_ID,
    ChatMessageRequest,
    ConversationResponse,
    LLMInfo,
)

DESTINATION_CATALOG_QUESTION = FLOW_QUESTIONS['destinations']
CHAT_SERVICE_UNAVAILABLE_ERROR = (
    'The chat service is temporarily unavailable. Please try again shortly.'
)
DEFAULT_CHAT_API_TIMEOUT_SECONDS = 180.0
DEFAULT_DEMO_RESPONSE_DELAY_MIN_SECONDS = 2.0
DEFAULT_DEMO_RESPONSE_DELAY_MAX_SECONDS = 3.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DemoResponseDelay:
    """Configurable delay used to simulate a demo response being generated."""

    min_seconds: float = DEFAULT_DEMO_RESPONSE_DELAY_MIN_SECONDS
    max_seconds: float = DEFAULT_DEMO_RESPONSE_DELAY_MAX_SECONDS

    def __post_init__(self) -> None:
        if self.min_seconds < 0:
            raise ValueError('The demo response delay minimum must be non-negative.')
        if self.max_seconds < self.min_seconds:
            raise ValueError(
                'The demo response delay maximum must be at least the minimum.'
            )


def demo_response_delay_from_environment() -> DemoResponseDelay:
    """Read the demo response delay from chat-specific environment settings."""
    try:
        min_seconds = float(
            os.getenv(
                'CHAT_DEMO_RESPONSE_DELAY_MIN_SECONDS',
                str(DEFAULT_DEMO_RESPONSE_DELAY_MIN_SECONDS),
            )
        )
        max_seconds = float(
            os.getenv(
                'CHAT_DEMO_RESPONSE_DELAY_MAX_SECONDS',
                str(DEFAULT_DEMO_RESPONSE_DELAY_MAX_SECONDS),
            )
        )
    except ValueError as exc:
        raise ValueError('Demo response delay settings must be numbers.') from exc
    return DemoResponseDelay(min_seconds=min_seconds, max_seconds=max_seconds)


def create_backend() -> ChatBackend:
    api_url = os.getenv('CHAT_API_URL')
    if api_url:
        delay = demo_response_delay_from_environment()
        return HttpChatBackend(
            api_url.rstrip('/'),
            demo_response_delay=(
                delay if os.getenv('AGENT_LLM_PROVIDER') == 'baguette-llm' else None
            ),
        )
    return DemoBackend()


class ChatBackend(ABC):
    """Client contract for backend-owned conversation sessions."""

    @abstractmethod
    async def start_chat(self) -> ConversationResponse:
        """Start a new conversation session."""

    @abstractmethod
    async def send_message(
        self,
        session_id: str,
        expected_step_id: str,
        input_id: str,
        text: str | None = None,
    ) -> ConversationResponse:
        """Submit a guided action or free-text message."""

    @abstractmethod
    async def submit_feedback(
        self, message_id: str, helpful: bool, comment: str | None = None
    ) -> None:
        """Submit feedback for a generated response."""

    @staticmethod
    def validate_response(payload: object) -> ConversationResponse:
        try:
            return ConversationResponse.model_validate(payload)
        except (TypeError, ValueError) as exc:
            raise RuntimeError('Invalid chat API response.') from exc


class DemoBackend(ChatBackend):
    """Deterministic development backend with server-like session state."""

    def __init__(self) -> None:
        self._sessions: dict[str, FlowStep] = {}

    async def start_chat(self) -> ConversationResponse:
        session_id = str(uuid4())
        self._sessions[session_id] = FlowStep.WELCOME
        return ConversationResponse(
            session_id=UUID(session_id),
            step_id=FlowStep.WELCOME,
            message=DEMO_WELCOME_MESSAGE,
            buttons=flow_definition(FlowStep.WELCOME).rendered_buttons(),
            llm=LLMInfo(provider='baguette-llm', model='mini-croissant-1.0'),
        )

    async def send_message(
        self,
        session_id: str,
        expected_step_id: str,
        input_id: str,
        text: str | None = None,
    ) -> ConversationResponse:
        request = ChatMessageRequest(
            session_id=UUID(session_id),
            expected_step_id=expected_step_id,
            input_id=input_id,
            text=text,
        )
        current_step = self._sessions.get(str(request.session_id))
        next_step = (
            transition_for(current_step, input_id, text=text)
            if current_step is not None and str(current_step) == expected_step_id
            else None
        )
        if next_step is None:
            raise RuntimeError('The input is invalid for this chat session.')
        if input_id == FREE_TEXT_INPUT_ID:
            message = NO_BACKEND_AVAILABLE_ANSWER
        elif input_id == 'destinations':
            message = 'This demo covers a handful of questions about Brittany.'
        else:
            message = IDENTITY_ANSWERS[FLOW_QUESTIONS[input_id]]
        self._sessions[str(request.session_id)] = next_step
        return ConversationResponse(
            session_id=request.session_id,
            step_id=next_step,
            message=message,
            buttons=flow_definition(next_step).rendered_buttons(),
        )

    async def submit_feedback(
        self, message_id: str, helpful: bool, comment: str | None = None
    ) -> None:
        del message_id, helpful, comment


class HttpChatBackend(ChatBackend):
    def __init__(
        self,
        api_url: str,
        timeout_seconds: float = DEFAULT_CHAT_API_TIMEOUT_SECONDS,
        *,
        demo_response_delay: DemoResponseDelay | None = None,
    ) -> None:
        self.api_url = api_url.rstrip('/')
        self.timeout = httpx.Timeout(timeout_seconds)
        self._demo_response_delay = demo_response_delay

    async def check_ready(self) -> None:
        """Verify that the API and knowledge base are ready."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f'{self.api_url.rsplit("/", 1)[0]}/health')
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError('The chat API is not ready.') from exc

    async def start_chat(self) -> ConversationResponse:
        return await self._post('/start', {})

    async def send_message(
        self,
        session_id: str,
        expected_step_id: str,
        input_id: str,
        text: str | None = None,
    ) -> ConversationResponse:
        request = ChatMessageRequest(
            session_id=UUID(session_id),
            expected_step_id=expected_step_id,
            input_id=input_id,
            text=text,
        )
        response = await self._post('/message', request.model_dump(mode='json'))
        if self._demo_response_delay is not None:
            await _wait_for_demo_response(self._demo_response_delay)
        return response

    async def _post(
        self, path: str, payload: dict[str, object]
    ) -> ConversationResponse:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f'{self.api_url}{path}', json=payload)
                response.raise_for_status()
        except httpx.ConnectError as exc:
            logger.exception('Unable to connect to the chat API')
            raise RuntimeError(CHAT_SERVICE_UNAVAILABLE_ERROR) from exc
        except httpx.HTTPStatusError as exc:
            logger.exception('The chat API returned an HTTP error')
            raise RuntimeError(CHAT_SERVICE_UNAVAILABLE_ERROR) from exc
        except httpx.HTTPError as exc:
            logger.exception('The chat API request failed')
            raise RuntimeError(CHAT_SERVICE_UNAVAILABLE_ERROR) from exc
        except ValueError as exc:
            logger.exception('The chat API returned an invalid response')
            raise RuntimeError(CHAT_SERVICE_UNAVAILABLE_ERROR) from exc
        return self.validate_response(response.json())

    async def submit_feedback(
        self, message_id: str, helpful: bool, comment: str | None = None
    ) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f'{self.api_url}/feedback',
                    json={
                        'message_id': message_id,
                        'helpful': helpful,
                        'comment': comment,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception('Unable to store feedback')
            raise RuntimeError(CHAT_SERVICE_UNAVAILABLE_ERROR) from exc


async def _wait_for_demo_response(delay: DemoResponseDelay) -> None:
    """Wait for a randomized demo response delay without blocking the event loop."""
    await asyncio.sleep(random.uniform(delay.min_seconds, delay.max_seconds))


__all__ = [
    'ChatBackend',
    'DemoBackend',
    'DemoResponseDelay',
    'HttpChatBackend',
    'create_backend',
    'demo_response_delay_from_environment',
]
