"""CLI adapter for the chunking stage."""

from pathlib import Path

import click
from pydantic import ValidationError

from ai_tour_guide.ingestion.pipeline import chunk_document_stage
from ai_tour_guide.ingestion.serialization import (
    CHUNKED_DOCUMENT_JSON,
    PARSED_DOCUMENT_JSON,
)
from ai_tour_guide.ingestion.settings import IngestionSettings


@click.command('chunk')
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
@click.option('--target-chars', type=click.IntRange(min=1), default=None)
@click.option('--max-chars', type=click.IntRange(min=1), default=None)
@click.option('--section-chunk-min-depth', type=click.IntRange(min=0), default=None)
@click.option('--section-chunk-max-depth', type=click.IntRange(min=0), default=None)
def chunk_command(
    input_path: Path,
    output_path: Path,
    target_chars: int | None,
    max_chars: int | None,
    section_chunk_min_depth: int | None,
    section_chunk_max_depth: int | None,
) -> None:
    """Read PARSED_DOCUMENT JSON and write CHUNKED_DOCUMENT JSON."""
    try:
        settings = IngestionSettings(
            **{
                key: value
                for key, value in {
                    'target_chars': target_chars,
                    'max_chars': max_chars,
                    'section_chunk_min_depth': section_chunk_min_depth,
                    'section_chunk_max_depth': section_chunk_max_depth,
                }.items()
                if value is not None
            }
        )
        result = chunk_document_stage(
            PARSED_DOCUMENT_JSON.read(input_path),
            config=settings.chunking_config,
        )
        destination = CHUNKED_DOCUMENT_JSON.write(result, output_path)
    except (OSError, RuntimeError, TypeError, ValueError, ValidationError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f'Generated {len(result.chunks)} chunks')
    click.echo(f'Wrote: {destination}')


__all__ = ['chunk_command']
