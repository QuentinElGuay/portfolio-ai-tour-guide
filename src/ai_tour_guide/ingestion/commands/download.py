"""CLI adapter for the PDF download stage."""

from pathlib import Path
from typing import TextIO

import click

from ai_tour_guide.ingestion.input import load_document
from ai_tour_guide.ingestion.io import write_bytes_atomic
from ai_tour_guide.ingestion.pipeline import download_pdf_stage


@click.command('download')
@click.argument('document', type=click.File('r', encoding='utf-8'))
@click.option(
    '--output',
    '-o',
    'output_path',
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
)
@click.option('--timeout', type=click.FloatRange(min=0.1), default=30.0)
def download_command(
    document: TextIO,
    output_path: Path,
    timeout: float,
) -> None:
    """Download one DOCUMENT definition to a local PDF file."""
    try:
        result = download_pdf_stage(
            load_document(document),
            timeout_seconds=timeout,
        )
        destination = write_bytes_atomic(result.content, output_path)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f'SHA-256: {result.source_checksum}')
    click.echo(f'Wrote: {destination}')


__all__ = ['download_command']
