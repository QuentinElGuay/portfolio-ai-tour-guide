"""Command group for independent and sequential ingestion stages."""

import click

from ai_tour_guide.ingestion.commands.chunk import chunk_command
from ai_tour_guide.ingestion.commands.download import download_command
from ai_tour_guide.ingestion.commands.embed import embed_command
from ai_tour_guide.ingestion.commands.load import load_command
from ai_tour_guide.ingestion.commands.parse import parse_command
from ai_tour_guide.ingestion.commands.run import run_command
from ai_tour_guide.ingestion.input import load_document, load_documents


@click.group(context_settings={'help_option_names': ['-h', '--help']})
def main() -> None:
    """Run individual ingestion stages or the complete pipeline."""


main.add_command(download_command)
main.add_command(parse_command)
main.add_command(chunk_command)
main.add_command(embed_command)
main.add_command(load_command)
main.add_command(run_command)

__all__ = ['load_document', 'load_documents', 'main']


if __name__ == '__main__':
    main()
