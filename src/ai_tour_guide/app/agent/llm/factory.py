"""Default language-model client selection."""

from ai_tour_guide.app.agent.demo_questions import DEFAULT_DEMO_DATASET_PATH
from ai_tour_guide.app.agent.llm.clients import LLMClient
from ai_tour_guide.app.agent.llm.clients.demo import DemoLLMClient
from ai_tour_guide.app.agent.llm.clients.gemini import GeminiClient
from ai_tour_guide.app.agent.llm.clients.openai import OpenAIClient
from ai_tour_guide.app.agent.llm.settings import (
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
            return DemoLLMClient(
                settings.demo_dataset_path or DEFAULT_DEMO_DATASET_PATH,
                close_question_distance=settings.close_question_distance,
                similar_question_distance=settings.similar_question_distance,
            )


__all__ = ['create_llm_client']
