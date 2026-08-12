"""Configuration for connecting to the knowledge-base database."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Settings loaded from the ``DB_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix='DB_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    user: str
    password: SecretStr
    host: str = 'localhost'
    port: int = Field(default=5432, gt=0)
    name: str


__all__ = ['DatabaseSettings']
