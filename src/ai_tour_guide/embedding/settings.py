from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_tour_guide.embedding.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_NORMALIZE,
)


class EmbeddingSettings(BaseSettings):
    """Configuration shared by document and query embedding."""

    model_config = SettingsConfigDict(
        env_prefix='EMBEDDING_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    model_name: str
    dimensions: int = Field(gt=0)
    batch_size: int = Field(default=DEFAULT_BATCH_SIZE, gt=0)
    normalize: bool = DEFAULT_NORMALIZE
    cache_dir: Path | None = None


__all__ = ['EmbeddingSettings']
