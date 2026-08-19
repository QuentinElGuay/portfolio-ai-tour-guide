"""Shared and provider-specific language-model settings."""

from enum import StrEnum

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_tour_guide.agent.llm.rate_limit import DEFAULT_REQUESTS_PER_SECOND


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENAI = 'openai'


class AgentsSettings(BaseSettings):
    """Effective agent configuration loaded from ``.env`` with overrides."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        populate_by_name=True,
    )

    llm_provider: LLMProvider = Field(
        default=LLMProvider.OPENAI,
        validation_alias='AGENT_LLM_PROVIDER',
    )
    api_key: SecretStr = Field(
        validation_alias='AGENT_LLM_API_KEY',
        description='Language-model API token',
    )
    model: str = Field(
        validation_alias='AGENT_LLM_MODEL',
        description='Language-model identifier',
    )
    requests_per_second: float = Field(
        default=DEFAULT_REQUESTS_PER_SECOND,
        gt=0,
        validation_alias='AGENT_LLM_REQUESTS_PER_SECOND',
    )


__all__ = ['AgentsSettings', 'LLMProvider']
