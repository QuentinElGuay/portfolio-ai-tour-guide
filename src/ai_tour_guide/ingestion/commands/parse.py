"""CLI adapter for the PDF parsing stage."""

import hashlib
from pathlib import Path
from typing import TextIO

import click

from ai_tour_guide.ingestion.artifacts import DownloadedPdf
from ai_tour_guide.ingestion.input import load_document
from ai_tour_guide.ingestion.pdf.serializers import (
    ParsedPdfMarkdownSerializer,
    ParsedPdfTextSerializer,
)
from ai_tour_guide.ingestion.pipeline import parse_pdf_stage
from ai_tour_guide.ingestion.serialization import PARSED_DOCUMENT_JSON


@click.command('parse')
@click.argument('document', type=click.File('r', encoding='utf-8'))
@click.argument(
    'pdf_path',
    type=click.Path(path_type=Path, exists=True, dir_okay=False, readable=True),
)
@click.option(
    '--output',
    '-o',
    'output_path',
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
)
@click.option('--text-output', type=click.Path(path_type=Path, dir_okay=False))
@click.option('--markdown-output', type=click.Path(path_type=Path, dir_okay=False))
def parse_command(
    document: TextIO,
    pdf_path: Path,
    output_path: Path,
    text_output: Path | None,
    markdown_output: Path | None,
) -> None:
    """Parse one local PDF using its DOCUMENT definition."""
    try:
        content = pdf_path.read_bytes()
        result = parse_pdf_stage(
            DownloadedPdf(
                document=load_document(document),
                content=content,
                source_checksum=hashlib.sha256(content).hexdigest(),
            )
        )
        destination = PARSED_DOCUMENT_JSON.write(result, output_path)
        if text_output is not None:
            ParsedPdfTextSerializer().write(result.parsed_pdf, text_output)
        if markdown_output is not None:
            ParsedPdfMarkdownSerializer().write(result.parsed_pdf, markdown_output)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f'Parsed {result.parsed_pdf.metadata.page_count} pages')
    click.echo(f'Wrote: {destination}')


__all__ = ['parse_command']
