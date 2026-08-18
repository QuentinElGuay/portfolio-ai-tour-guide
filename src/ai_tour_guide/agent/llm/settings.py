"""Shared and provider-specific language-model settings."""

from abc import ABC

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_tour_guide.agent.llm.rate_limit import DEFAULT_REQUESTS_PER_SECOND


class LLMSettings(BaseSettings, ABC):
    """Provider-neutral settings shared by language-model clients."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    api_key: SecretStr = Field(description='Language-model API token')
    model: str = Field(description='Language-model identifier')
    requests_per_second: float = Field(default=DEFAULT_REQUESTS_PER_SECOND, gt=0)


class OpenAISettings(LLMSettings):
    """Settings loaded from the ``AGENT_OPENAI_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix='AGENT_OPENAI_')


__all__ = ['LLMSettings', 'OpenAISettings']
