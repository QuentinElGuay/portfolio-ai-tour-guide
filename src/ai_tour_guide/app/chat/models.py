from enum import StrEnum
from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FREE_TEXT_INPUT_ID = 'FREE_TEXT'


class Emotion(StrEnum):
    """Emotions available for rendering alongside an assistant answer."""

    CONFUSED = 'confused'
    DISAPPOINTED = 'disappointed'
    HAPPY = 'happy'
    NEUTRAL = 'neutral'


class Role(StrEnum):
    """Roles supported by the agent chat protocol."""

    USER = 'user'
    ASSISTANT = 'assistant'
    SYSTEM = 'system'


class Message(TypedDict):
    role: Role
    content: str


class ChatHistoryItem(TypedDict):
    """One message-shaped item supplied by Gradio's chat history."""

    role: str
    content: object


class ConversationButton(BaseModel):
    """A backend-defined action that a generic client can render."""

    model_config = ConfigDict(extra='forbid')

    input_id: str = Field(min_length=1)
    label: str = Field(min_length=1)

    @field_validator('input_id', 'label')
    @classmethod
    def normalize_text(cls, value: str) -> str:
        """Reject blank identifiers and labels while normalizing whitespace."""
        value = value.strip()
        if not value:
            raise ValueError('must not be empty')
        return value


class ConversationTrace(BaseModel):
    """Safe operational metadata for one generated answer."""

    model_config = ConfigDict(extra='forbid')

    intent: str = Field(min_length=1)
    actions: list[str] = Field(default_factory=list)
    tool_inputs: list[str] = Field(default_factory=list)
    tool_call_count: int = Field(default=0, ge=0)
    evidence_sufficient: bool = False
    retries: int = Field(default=0, ge=0)
    final_status: str = Field(min_length=1)


class ChatMessageRequest(BaseModel):
    """One client-independent interaction in an existing chat session."""

    model_config = ConfigDict(extra='forbid')

    session_id: UUID
    expected_step_id: str = Field(min_length=1)
    input_id: str = Field(min_length=1)
    text: str | None = None

    @field_validator('expected_step_id', 'input_id')
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('must not be empty')
        return value

    @field_validator('text')
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode='after')
    def validate_free_text(self) -> ChatMessageRequest:
        if self.input_id == FREE_TEXT_INPUT_ID and not self.text:
            raise ValueError('text must be non-empty when input_id is FREE_TEXT')
        return self


class ConversationResponse(BaseModel):
    """Renderable response returned by chat start and message operations."""

    model_config = ConfigDict(extra='forbid')

    session_id: UUID
    step_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    buttons: list[ConversationButton] = Field(default_factory=list)
    request_id: UUID | None = None
    sources: list[dict[str, object]] = Field(default_factory=list)
    trace: ConversationTrace | None = None

    @field_validator('step_id', 'message')
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('must not be empty')
        return value


class ChatErrorCode(StrEnum):
    """Stable error categories exposed by the chat API."""

    INVALID_SESSION = 'invalid_session'
    STALE_STEP = 'stale_expected_step_id'
    INVALID_ACTION = 'invalid_action'
    INVALID_TEXT = 'invalid_text'


class ChatErrorResponse(BaseModel):
    """Safe, machine-readable error payload for invalid chat interactions."""

    code: ChatErrorCode
    message: str = Field(min_length=1)


class ChatFeedbackRequest(BaseModel):
    """Feedback associated with a generated chat response."""

    model_config = ConfigDict(extra='forbid')

    request_id: UUID
    helpful: bool
    comment: str | None = None

    @field_validator('comment')
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ChatFeedbackResponse(BaseModel):
    """Confirmation that feedback was linked to a generated response."""

    request_id: UUID


__all__ = [
    'FREE_TEXT_INPUT_ID',
    'ChatErrorCode',
    'ChatErrorResponse',
    'ChatFeedbackRequest',
    'ChatFeedbackResponse',
    'ChatHistoryItem',
    'ChatMessageRequest',
    'ConversationButton',
    'ConversationResponse',
    'ConversationTrace',
    'Emotion',
    'Message',
    'Role',
]
