from enum import StrEnum
from typing import TypedDict


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


__all__ = ['ChatHistoryItem', 'Emotion', 'Message', 'Role']
