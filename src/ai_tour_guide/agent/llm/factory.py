"""Default language-model client selection."""

from ai_tour_guide.agent.llm.clients import LLMClient, LLMProvider, OpenAIClient
from ai_tour_guide.agent.llm.settings import AgentsSettings


def create_llm_client(settings: AgentsSettings) -> LLMClient:
    """Create the configured client for ``provider``."""

    if not settings.api_key.get_secret_value().strip():
        raise ValueError('An LLM API key must be provided.')

    match settings.llm_provider:
        case LLMProvider.OPENAI:
            return OpenAIClient(settings)


__all__ = ['create_llm_client']
