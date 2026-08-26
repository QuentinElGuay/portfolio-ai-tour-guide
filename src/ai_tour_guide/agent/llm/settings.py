"""Shared and provider-specific language-model settings."""

from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_tour_guide.agent.llm.rate_limit import DEFAULT_REQUESTS_PER_SECOND

DEFAULT_BAGUETTE_LLM_DATASET_PATH = Path('evaluation/datasets/golden_dataset.jsonl')


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENAI = 'openai'
    FIXTURE = 'fixture'
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
    fixture_dataset_path: Path | None = Field(
        default=None,
        validation_alias='AGENT_LLM_FIXTURE_DATASET',
        description='Golden dataset used by the deterministic fixture LLM',
    )


__all__ = ['DEFAULT_BAGUETTE_LLM_DATASET_PATH', 'AgentsSettings', 'LLMProvider']
