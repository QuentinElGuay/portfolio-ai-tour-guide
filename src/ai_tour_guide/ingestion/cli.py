"""Command-line interface for downloading and parsing a tourism guide."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, TextIO

import click
from pydantic import ValidationError

from ai_tour_guide.ingestion.pdf.markdown import write_markdown
from ai_tour_guide.ingestion.pdf.parser import (
    IngestionDocument,
    IngestionSettings,
    PdfDownloadError,
    PdfParseError,
    download_pdf,
    parse_pdf,
)

LOGGER = logging.getLogger(__name__)


def load_documents(source: TextIO) -> tuple[IngestionDocument, ...]:
    """Load one or more ingestion documents from a JSON stream."""
    try:
        payload = json.load(source)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f'Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}'
        ) from exc

    if isinstance(payload, dict):
        document_values = [payload]
    elif isinstance(payload, list):
        if not payload:
            raise ValueError('The ingestion document array must not be empty')
        document_values = payload
    else:
        raise ValueError(
            'The ingestion input must be a JSON object or an array of JSON objects'
        )

    documents: list[IngestionDocument] = []
    for index, values in enumerate(document_values, start=1):
        if not isinstance(values, dict):
            raise ValueError(f'Document {index} must be a JSON object')
        try:
            documents.append(IngestionDocument.from_dict(values))
        except ValueError as exc:
            raise ValueError(f'Invalid document {index}: {exc}') from exc

    filename_stems = [document.filename_stem for document in documents]
    duplicate_filenames = sorted(
        stem for stem in set(filename_stems) if filename_stems.count(stem) > 1
    )
    if duplicate_filenames:
        raise ValueError(
            'Document titles must produce unique filenames; duplicate filename stem(s): '
            + ', '.join(duplicate_filenames)
        )

    return tuple(documents)


def load_settings(**cli_values: Any) -> IngestionSettings:
    """Load settings, applying only explicitly supplied CLI options."""
    overrides = {name: value for name, value in cli_values.items() if value is not None}
    return IngestionSettings(**overrides)


def chunk_document_text(text: str) -> tuple[str, ...]:
    """Mock document chunking step.

    Replace this implementation with the project's real chunking strategy.
    For now, the complete parsed text is returned as a single chunk.
    """
    normalized_text = text.strip()
    return (normalized_text,) if normalized_text else ()


def load_chunks_to_database(
    document: IngestionDocument,
    chunks: tuple[str, ...],
) -> None:
    """Mock database-loading step.

    Replace this function with the real persistence or vector-store adapter.
    """
    LOGGER.info(
        'Mock database load for %s: %d chunk(s)',
        document.title,
        len(chunks),
    )


def ingest_document(
    document: IngestionDocument,
    settings: IngestionSettings,
) -> None:
    """Execute every ingestion step for one source PDF."""
    filename_stem = document.filename_stem
    output_paths = {
        'pdf': settings.tmp_folder / f'{filename_stem}.pdf',
        'markdown': settings.tmp_folder / f'{filename_stem}.md',
        'text': settings.tmp_folder / f'{filename_stem}.txt',
        'json': settings.tmp_folder / f'{filename_stem}.json',
    }

    # Create the shared output folder once for this document's artifacts.
    settings.tmp_folder.mkdir(parents=True, exist_ok=True)

    # 1. Download the source PDF.
    pdf_output_path = output_paths['pdf']
    pdf_path = download_pdf(
        document.pdf_url,
        pdf_output_path,
        timeout_seconds=settings.timeout,
    )

    # 2. Parse the downloaded PDF.
    parsed_pdf = parse_pdf(document)

    # 3. Write generated artifacts.
    text_output_path = output_paths['text']
    text_output_path.write_text(parsed_pdf.text, encoding='utf-8')

    markdown_output_path = output_paths['markdown']
    write_markdown(parsed_pdf, markdown_output_path)

    json_output_path = output_paths['json']
    parsed_pdf.write_json(json_output_path)

    # 4. Chunk the parsed text and load the chunks into the database.
    chunks = chunk_document_text(parsed_pdf.text)
    load_chunks_to_database(document, chunks)

    LOGGER.info('Downloaded PDF to %s', pdf_path)
    LOGGER.info(
        'Extracted %d pages to %s',
        parsed_pdf.metadata.page_count,
        text_output_path,
    )


@click.command()
@click.argument(
    'document',
    type=click.File('r', encoding='utf-8'),
)
@click.option(
    '--tmp-folder',
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help='Folder for downloaded and generated files. Overrides INGESTION_TMP_FOLDER.',
)
@click.option(
    '--timeout',
    type=click.FloatRange(min=0.1),
    default=None,
    help='HTTP timeout in seconds. Overrides INGESTION_TIMEOUT.',
)
@click.option(
    '--verbose/--no-verbose',
    default=None,
    help='Enable or disable debug logging. Overrides INGESTION_VERBOSE.',
)
def main(
    document: TextIO,
    tmp_folder: Path | None,
    timeout: float | None,
    verbose: bool | None,
) -> None:
    """Download and parse the PDFs described by DOCUMENT.

    DOCUMENT is a JSON file path containing either one document object or an
    array of document objects. Use '-' to read JSON from stdin.
    """
    try:
        ingestion_documents = load_documents(document)
        settings = load_settings(
            tmp_folder=tmp_folder,
            timeout=timeout,
            verbose=verbose,
        )
    except (ValueError, ValidationError) as exc:
        raise click.ClickException(f'Invalid ingestion configuration:\n{exc}') from exc

    logging.basicConfig(
        level=logging.DEBUG if settings.verbose else logging.INFO,
        format='%(levelname)s: %(message)s',
    )

    document_count = len(ingestion_documents)

    # Process each source PDF sequentially. A document completes all ingestion
    # steps before the next document starts.
    for index, ingestion_document in enumerate(ingestion_documents, start=1):
        LOGGER.info(
            'Ingesting document %d/%d: %s (%s)',
            index,
            document_count,
            ingestion_document.title,
            ingestion_document.pdf_url,
        )

        try:
            ingest_document(ingestion_document, settings)
        except (PdfDownloadError, PdfParseError, OSError) as exc:
            raise click.ClickException(
                f'Failed to ingest document {index}/{document_count} '
                f'({ingestion_document.title}, '
                f'{ingestion_document.pdf_url}): {exc}'
            ) from exc


if __name__ == '__main__':
    main()
