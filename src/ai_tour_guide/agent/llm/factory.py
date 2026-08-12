"""Default language-model client selection."""

from pydantic import ValidationError

from ai_tour_guide.agent.llm.client import OpenAIClient
from ai_tour_guide.agent.llm.interfaces import LLMClient
from ai_tour_guide.agent.llm.settings import OpenAISettings


def create_default_llm_client() -> LLMClient | None:
    """Create the configured default client, if one is available."""
    try:
        # Currently, only OpenAI is accepted.
        # In future versions, we might allow for other providers
        # and multiple client at the same time.
        settings = OpenAISettings()
    except ValidationError:
        return None

    if not settings.api_key.get_secret_value().strip():
        return None

    return OpenAIClient(settings)


__all__ = ['create_default_llm_client']
