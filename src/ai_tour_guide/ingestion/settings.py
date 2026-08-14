from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_tour_guide.ingestion.constants import (
    DEFAULT_MAX_CHARS,
    DEFAULT_SECTION_MAX_DEPTH,
    DEFAULT_SECTION_MIN_DEPTH,
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
    min_depth: int = Field(default=DEFAULT_SECTION_MIN_DEPTH, gt=0)
    max_depth: int = Field(default=DEFAULT_SECTION_MAX_DEPTH, gt=0)

    def model_post_init(self, __context: object, /) -> None:
        if self.target_chars > self.max_chars:
            raise ValueError('target_chars must be less than or equal to max_chars')
        if self.max_depth < self.min_depth:
            raise ValueError('max_depth must be greater than or equal to min_depth')
