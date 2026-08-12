"""Provider-neutral interfaces for language-model clients."""

from collections.abc import Sequence
from typing import Protocol

from ai_tour_guide.agent.chat.models import Message


class LLMClient(Protocol):
    """Generate a reply from a complete conversation."""

    async def generate_reply(self, messages: Sequence[Message]) -> str:
        """Return the generated reply for ``messages``."""


__all__ = ['LLMClient']
