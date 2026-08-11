"""CLI adapter for the embedding stage."""

from pathlib import Path

import click

from ai_tour_guide.embedding import (
    DEFAULT_BATCH_SIZE,
    FastEmbedder,
)
from ai_tour_guide.embedding.settings import EmbeddingSettings
from ai_tour_guide.ingestion.pipeline import embed_document_stage
from ai_tour_guide.ingestion.serialization import (
    CHUNKED_DOCUMENT_JSON,
    EMBEDDED_DOCUMENT_JSON,
)


@click.command('embed')
@click.argument(
    'input_path',
    type=click.Path(path_type=Path, exists=True, dir_okay=False, readable=True),
)
@click.option(
    '--output',
    '-o',
    'output_path',
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
)
@click.option('--batch-size', type=click.IntRange(min=1), default=DEFAULT_BATCH_SIZE)
@click.option('--normalize/--no-normalize', default=True)
def embed_command(
    input_path: Path,
    output_path: Path,
    batch_size: int,
    normalize: bool,
) -> None:
    """Read CHUNKED_DOCUMENT JSON and write EMBEDDED_DOCUMENT JSON."""
    try:
        embedding_settings = EmbeddingSettings()
        embedder = FastEmbedder(
            model_name=embedding_settings.model_name,
            normalize=normalize,
            cache_dir=embedding_settings.cache_dir,
        )
        result = embed_document_stage(
            CHUNKED_DOCUMENT_JSON.read(input_path),
            embedder=embedder,
            batch_size=batch_size,
        )
        destination = EMBEDDED_DOCUMENT_JSON.write(result, output_path)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f'Embedded {len(result.chunks)} chunks')
    click.echo(f'Wrote: {destination}')


__all__ = ['embed_command']
