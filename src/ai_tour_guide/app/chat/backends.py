import os
from abc import ABC, abstractmethod
from uuid import UUID, uuid4

import httpx

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
)

DESTINATION_CATALOG_QUESTION = FLOW_QUESTIONS['destinations']


def create_backend() -> ChatBackend:
    api_url = os.getenv('CHAT_API_URL')
    return HttpChatBackend(api_url.rstrip('/')) if api_url else DemoBackend()


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
            message='Welcome to Bon Voyage. How can I help you prepare your trip?',
            buttons=flow_definition(FlowStep.WELCOME).rendered_buttons(),
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
    def __init__(self, api_url: str, timeout_seconds: float = 60.0) -> None:
        self.api_url = api_url.rstrip('/')
        self.timeout = httpx.Timeout(timeout_seconds)

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
        return await self._post('/message', request.model_dump(mode='json'))

    async def _post(
        self, path: str, payload: dict[str, object]
    ) -> ConversationResponse:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f'{self.api_url}{path}', json=payload)
                response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError('Unable to connect to the chat API.') from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f'The chat API returned HTTP {exc.response.status_code}.'
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f'Chat API request failed: {exc}') from exc
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
            raise RuntimeError(f'Unable to store feedback: {exc}') from exc


__all__ = ['ChatBackend', 'DemoBackend', 'HttpChatBackend', 'create_backend']
