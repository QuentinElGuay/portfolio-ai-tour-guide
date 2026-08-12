"""Default language-model client selection."""

from pydantic import ValidationError

from ai_tour_guide.agent.llm.client import OpenAIClient
from ai_tour_guide.agent.llm.interfaces import LLMClient
from ai_tour_guide.agent.llm.settings import OpenAISettings


def create_default_llm_client() -> LLMClient | None:
    """Create the configured default client, if one is available."""
    try:
        return OpenAIClient(OpenAISettings())
    except ValidationError:
        return None


__all__ = ['create_default_llm_client']
