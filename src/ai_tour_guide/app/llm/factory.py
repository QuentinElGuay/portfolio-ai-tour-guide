"""Default language-model client selection."""

from ai_tour_guide.app.llm.clients import LLMClient
from ai_tour_guide.app.llm.clients.gemini import GeminiClient
from ai_tour_guide.app.llm.clients.openai import OpenAIClient
from ai_tour_guide.app.llm.settings import (
    AgentsSettings,
    LLMProvider,
)


def create_llm_client(settings: AgentsSettings) -> LLMClient:
    """Create the configured client for ``provider``."""

    match settings.llm_provider:
        case LLMProvider.OPENAI:
            if not settings.api_key.get_secret_value().strip():
                raise ValueError('An LLM API key must be provided.')
            return OpenAIClient(settings)
        case LLMProvider.GEMINI:
            if not settings.api_key.get_secret_value().strip():
                raise ValueError('An LLM API key must be provided.')
            return GeminiClient(settings)
        case LLMProvider.BAGUETTE_LLM:
            raise ValueError(
                'baguette-llm is served by DeterministicTravelAgent and cannot use '
                'the RAG client.'
            )


__all__ = ['create_llm_client']
