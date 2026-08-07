from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
