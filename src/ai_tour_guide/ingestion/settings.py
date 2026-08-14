from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_tour_guide.ingestion.config import ChunkingConfig
from ai_tour_guide.ingestion.constants import (
    DEFAULT_MAX_CHARS,
    DEFAULT_TARGET_CHARS,
)

TMP_FOLDER = Path('tmp')


class IngestionSettings(BaseSettings):
    """Operational configuration for the ingestion pipeline."""

    model_config = SettingsConfigDict(
        env_prefix='INGESTION_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    tmp_folder: Path = TMP_FOLDER
    timeout: float = Field(default=30.0, gt=0)
    debug: bool = False
    target_chars: int = Field(default=DEFAULT_TARGET_CHARS, gt=0)
    max_chars: int = Field(default=DEFAULT_MAX_CHARS, gt=0)
    section_chunk_min_depth: int | None = Field(default=None, ge=0)
    section_chunk_max_depth: int | None = Field(default=None, ge=0)

    @property
    def chunking_config(self) -> ChunkingConfig:
        """Return the chunking configuration resolved from settings."""
        return ChunkingConfig(
            target_chars=self.target_chars,
            max_chars=self.max_chars,
            section_chunk_min_depth=self.section_chunk_min_depth,
            section_chunk_max_depth=self.section_chunk_max_depth,
        )
