"""Shared language-model client contracts and implementations."""

from collections.abc import Sequence
from typing import Protocol

from ai_tour_guide.app.agent.rag.models import GeneratedAnswer
from ai_tour_guide.app.chat.models import Message


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


class NoContextFallbackClient:
    """Provide a deterministic answer when retrieval returns no evidence."""

    async def answer_without_context(self, question: str) -> GeneratedAnswer:
        """Return a user-facing fallback for an unsupported question."""
        raise NotImplementedError


from ai_tour_guide.app.agent.llm.clients.demo import DemoLLMClient
from ai_tour_guide.app.agent.llm.clients.gemini import (
    GeminiClient,
    create_gemini_client,
)
from ai_tour_guide.app.agent.llm.clients.openai import (
    OpenAIClient,
    _parse_answer,
    create_openai_client,
)

__all__ = [
    'AgentLLMClient',
    'DemoLLMClient',
    'GeminiClient',
    'GenerationError',
    'LLMClient',
    'NoContextFallbackClient',
    'OpenAIClient',
    '_parse_answer',
    'create_gemini_client',
    'create_openai_client',
]
