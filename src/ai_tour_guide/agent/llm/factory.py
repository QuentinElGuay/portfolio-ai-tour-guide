"""Default language-model client selection."""

from ai_tour_guide.agent.llm.clients import LLMClient, OpenAIClient
from ai_tour_guide.agent.llm.fixture import BaguetteLLMClient, FixtureLLMClient
from ai_tour_guide.agent.llm.settings import (
    DEFAULT_BAGUETTE_LLM_DATASET_PATH,
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
        case LLMProvider.FIXTURE:
            if settings.fixture_dataset_path is None:
                raise ValueError('A fixture dataset path must be provided.')
            return FixtureLLMClient(settings.fixture_dataset_path)
        case LLMProvider.BAGUETTE_LLM:
            return BaguetteLLMClient(
                DEFAULT_BAGUETTE_LLM_DATASET_PATH,
                close_question_distance=settings.close_question_distance,
                similar_question_distance=settings.similar_question_distance,
            )


__all__ = ['create_llm_client']
