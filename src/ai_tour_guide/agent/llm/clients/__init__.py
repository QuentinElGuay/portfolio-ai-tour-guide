"""Shared language-model client contracts and implementations."""

from collections.abc import Sequence
from typing import Protocol

from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.rag.models import GeneratedAnswer


class GenerationError(RuntimeError):
    """An expected provider or structured-output failure."""


class LLMClient(Protocol):
    """Generate replies and choose retrieval queries."""

    async def answer_question(self, messages: Sequence[Message]) -> GeneratedAnswer:
        """Return a structured answer for ``messages``."""
        ...

    async def choose_search_query(
        self,
        question: str,
        *,
        previous_queries: Sequence[str],
        has_context: bool,
    ) -> str | None:
        """Choose a retrieval query, or no query for a direct response."""
        ...


AgentLLMClient = LLMClient

from ai_tour_guide.agent.llm.clients.demo import DemoLLMClient
from ai_tour_guide.agent.llm.clients.openai import (
    OpenAIClient,
    _parse_answer,
    create_openai_client,
)

__all__ = [
    'AgentLLMClient',
    'DemoLLMClient',
    'GenerationError',
    'LLMClient',
    'OpenAIClient',
    '_parse_answer',
    'create_openai_client',
]
