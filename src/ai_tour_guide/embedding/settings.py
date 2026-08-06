from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_tour_guide.embedding.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MODEL_NAME,
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

    model_name: str = DEFAULT_MODEL_NAME
    batch_size: int = Field(default=DEFAULT_BATCH_SIZE, gt=0)
    normalize: bool = DEFAULT_NORMALIZE
