from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class Role(StrEnum):
    """Roles supported by the agent chat protocol."""

    USER = 'user'
    ASSISTANT = 'assistant'
    SYSTEM = 'system'


class Message(TypedDict):
    role: Role
    content: str
