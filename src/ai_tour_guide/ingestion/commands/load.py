"""CLI adapter for the knowledge-base loading stage."""

from pathlib import Path

import click

from ai_tour_guide.ingestion.pipeline import load_document_stage
from ai_tour_guide.ingestion.serialization import EMBEDDED_DOCUMENT_JSON


@click.command('load')
@click.argument(
    'input_path',
    type=click.Path(path_type=Path, exists=True, dir_okay=False, readable=True),
)
def load_command(input_path: Path) -> None:
    """Load one EMBEDDED_DOCUMENT JSON artifact into PostgreSQL."""
    try:
        document_id = load_document_stage(EMBEDDED_DOCUMENT_JSON.read(input_path))
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f'Inserted document_id={document_id}')


__all__ = ['load_command']
