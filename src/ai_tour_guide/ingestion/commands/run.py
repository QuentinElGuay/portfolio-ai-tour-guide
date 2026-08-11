"""CLI adapter for sequential in-memory ingestion orchestration."""

import logging
from pathlib import Path
from typing import TextIO

import click
from pydantic import ValidationError

from ai_tour_guide.embedding import FastEmbedder
from ai_tour_guide.embedding.settings import EmbeddingSettings
from ai_tour_guide.ingestion.input import load_documents
from ai_tour_guide.ingestion.pipeline import run_pipeline
from ai_tour_guide.ingestion.settings import IngestionSettings

LOGGER = logging.getLogger(__name__)


@click.command('run')
@click.argument('documents', type=click.File('r', encoding='utf-8'))
@click.option(
    '--artifact-dir',
    'tmp_folder',
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help='Directory for artifacts retained by --debug.',
)
@click.option('--timeout', type=click.FloatRange(min=0.1), default=None)
@click.option('--debug/--no-debug', default=None)
@click.option('--target-chars', type=click.IntRange(min=1), default=750)
@click.option('--max-chars', type=click.IntRange(min=1), default=1_000)
def run_command(
    documents: TextIO,
    tmp_folder: Path | None,
    timeout: float | None,
    debug: bool | None,
    target_chars: int,
    max_chars: int,
) -> None:
    """Run all ingestion stages sequentially for one or more DOCUMENTS."""
    try:
        ingestion_documents = load_documents(documents)
        settings_values = {
            name: value
            for name, value in {
                'tmp_folder': tmp_folder,
                'timeout': timeout,
                'debug': debug,
            }.items()
            if value is not None
        }
        ingestion_settings = IngestionSettings(**settings_values)
        embedding_settings = EmbeddingSettings()
        embedder = FastEmbedder(
            model_name=embedding_settings.model_name,
            normalize=embedding_settings.normalize,
            cache_dir=embedding_settings.cache_dir,
        )

        logging.basicConfig(
            level=logging.DEBUG if ingestion_settings.debug else logging.INFO,
            format='%(levelname)s: %(message)s',
        )

        document_ids = run_pipeline(
            ingestion_documents,
            settings=ingestion_settings,
            embedder=embedder,
            embedding_batch_size=embedding_settings.batch_size,
            target_chars=target_chars,
            max_chars=max_chars,
        )
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc

    for document, document_id in zip(
        ingestion_documents,
        document_ids,
        strict=True,
    ):
        LOGGER.info('Inserted %s as document_id=%d', document.title, document_id)

    click.echo(f'Ingested {len(document_ids)} document(s)')


__all__ = ['run_command']
