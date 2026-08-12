"""Provider-neutral interfaces for language-model clients."""

from collections.abc import Sequence
from typing import Protocol

from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.rag.models import GeneratedAnswer


class GenerationError(RuntimeError):
    """An expected provider or structured-output failure."""


class LLMClient(Protocol):
    """Generate a reply from a complete conversation."""

    async def answer_question(self, messages: Sequence[Message]) -> GeneratedAnswer:
        """Return a structured answer for ``messages``."""


__all__ = ['GenerationError', 'LLMClient']
