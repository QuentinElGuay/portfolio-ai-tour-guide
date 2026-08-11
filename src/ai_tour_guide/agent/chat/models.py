from __future__ import annotations

from typing import Literal, TypedDict


Role = Literal["user", "assistant", "system"]


class Message(TypedDict):
    role: Role
    content: str
