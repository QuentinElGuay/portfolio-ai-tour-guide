"""Configuration for connecting to the knowledge-base database."""

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

POSTGRES_IDENTIFIER_PATTERN = r'^[a-z_][a-z0-9_]*$'


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
    schema_name: str = Field(
        default='public',
        validation_alias=AliasChoices('schema_name', 'DB_SCHEMA'),
        pattern=POSTGRES_IDENTIFIER_PATTERN,
    )


__all__ = ['POSTGRES_IDENTIFIER_PATTERN', 'DatabaseSettings']
