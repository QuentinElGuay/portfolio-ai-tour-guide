"""Shared and provider-specific language-model settings."""

from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_tour_guide.agent.llm.rate_limit import DEFAULT_REQUESTS_PER_SECOND

DEFAULT_CLOSE_QUESTION_DISTANCE = 0.25
DEFAULT_SIMILAR_QUESTION_DISTANCE = 0.50


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENAI = 'openai'
    BAGUETTE_LLM = 'baguette-llm'


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
        default=SecretStr(''),
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
    demo_dataset_path: Path | None = Field(
        default=None,
        validation_alias='AGENT_LLM_DEMO_DATASET',
        description='Standalone response dataset used by demo or test runs',
    )
    close_question_distance: float = Field(
        default=DEFAULT_CLOSE_QUESTION_DISTANCE,
        ge=0,
        le=1,
        validation_alias='AGENT_CLOSE_QUESTION_DISTANCE',
        description='Maximum normalized distance for an exact demo answer',
    )
    similar_question_distance: float = Field(
        default=DEFAULT_SIMILAR_QUESTION_DISTANCE,
        ge=0,
        le=1,
        validation_alias='AGENT_SIMILAR_QUESTION_DISTANCE',
        description='Maximum normalized distance for a demo question suggestion',
    )


__all__ = [
    'DEFAULT_CLOSE_QUESTION_DISTANCE',
    'DEFAULT_SIMILAR_QUESTION_DISTANCE',
    'AgentsSettings',
    'LLMProvider',
]
