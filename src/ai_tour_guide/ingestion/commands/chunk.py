"""CLI adapter for the chunking stage."""

from pathlib import Path

import click

from ai_tour_guide.ingestion.pipeline import chunk_document_stage
from ai_tour_guide.ingestion.serialization import (
    CHUNKED_DOCUMENT_JSON,
    PARSED_DOCUMENT_JSON,
)


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
@click.option('--target-chars', type=click.IntRange(min=1), default=750)
@click.option('--max-chars', type=click.IntRange(min=1), default=1_000)
def chunk_command(
    input_path: Path,
    output_path: Path,
    target_chars: int,
    max_chars: int,
) -> None:
    """Read PARSED_DOCUMENT JSON and write CHUNKED_DOCUMENT JSON."""
    try:
        result = chunk_document_stage(
            PARSED_DOCUMENT_JSON.read(input_path),
            target_chars=target_chars,
            max_chars=max_chars,
        )
        destination = CHUNKED_DOCUMENT_JSON.write(result, output_path)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f'Generated {len(result.chunks)} chunks')
    click.echo(f'Wrote: {destination}')


__all__ = ['chunk_command']
