"""Default language-model client selection."""

from ai_tour_guide.agent.llm.clients import LLMClient, OpenAIClient
from ai_tour_guide.agent.llm.fixture import FixtureLLMClient
from ai_tour_guide.agent.llm.settings import AgentsSettings, LLMProvider


def create_llm_client(settings: AgentsSettings) -> LLMClient:
    """Create the configured client for ``provider``."""

    match settings.llm_provider:
        case LLMProvider.OPENAI:
            if not settings.api_key.get_secret_value().strip():
                raise ValueError('An LLM API key must be provided.')
            return OpenAIClient(settings)
        case LLMProvider.FIXTURE:
            if settings.fixture_dataset_path is None:
                raise ValueError('A fixture dataset path must be provided.')
            return FixtureLLMClient(settings.fixture_dataset_path)


__all__ = ['create_llm_client']
