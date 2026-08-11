"""Configuration for direct OpenAI language-model calls."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAISettings(BaseSettings):
    """Settings loaded from the ``AGENT_OPENAI_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix='AGENT_OPENAI_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    api_key: SecretStr = Field(description='OpenAI API token')
    model: str = 'gpt-4.1-mini'


__all__ = ['OpenAISettings']
