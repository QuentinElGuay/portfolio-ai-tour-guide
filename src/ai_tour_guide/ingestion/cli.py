"""Command-line interface for downloading and parsing a tourism guide."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import logging
from pathlib import Path
from typing import Any, TextIO

import click
from pydantic import ValidationError

from ai_tour_guide import database
from ai_tour_guide.embedding.fastembed import FastEmbedder
from ai_tour_guide.embedding.interfaces import Embedder
from ai_tour_guide.embedding.settings import EmbeddingSettings
from ai_tour_guide.ingestion.chunking import chunk_document
from ai_tour_guide.ingestion.embedding import embed_chunks
from ai_tour_guide.ingestion.pdf.markdown import write_markdown
from ai_tour_guide.ingestion.pdf.parser import (
    IngestionDocument,
    PdfDownloadError,
    PdfParseError,
    download_pdf,
    parse_pdf,
)
from ai_tour_guide.ingestion.settings import IngestionSettings

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


def load_document_and_chunks_to_database(
    document: Mapping[str, Any],
    chunks: Sequence[Mapping[str, Any]],
) -> None:
    """Upsert one document and replace its associated chunks."""
    with database.transaction() as transaction:
        document_id = transaction.upsert_document(
            document,
            conflict_column='pdf_url',
        )

        chunk_rows = [
            {
                'document_id': document_id,
                **chunk,
            }
            for chunk in chunks
        ]

        current_chunk_ids = [str(chunk['chunk_id']) for chunk in chunks]

        # Prevent obsolete chunks from remaining after re-ingestion.
        transaction.delete_stale_chunks(
            document_id=document_id,
            current_chunk_ids=current_chunk_ids,
        )

        transaction.upsert_chunks(
            chunk_rows,
            conflict_columns=('document_id', 'chunk_id'),
        )


def ingest_document(
    document: IngestionDocument,
    settings: IngestionSettings,
    embedder: Embedder,
    embedding_batch_size: int,
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

    # 3. Write debugging/intermediate artifacts.
    output_paths['text'].write_text(parsed_pdf.text, encoding='utf-8')
    write_markdown(parsed_pdf, output_paths['markdown'])
    parsed_pdf.write_json(output_paths['json'])

    # 4. Produce structure-aware chunks.
    chunk_objects = chunk_document(parsed_pdf.to_dict())
    chunk_records = [chunk.to_dict() for chunk in chunk_objects]

    if not chunk_records:
        raise ValueError(f'No chunks were produced for document {document.title!r}')

    LOGGER.info(
        'Generated %d chunks for %s',
        len(chunk_records),
        document.title,
    )

    # 5. Generate embeddings.
    embedding_result = embed_chunks(
        [chunk.to_dict() for chunk in chunk_records],
        embedder=embedder,
        batch_size=embedding_batch_size,
    )

    LOGGER.info(
        'Embedded %d chunks using %s (%d dimensions)',
        len(embedding_result.chunks),
        embedding_result.model_name,
        embedding_result.dimensions,
    )

    # 6. Upload the document and its embedded chunks.
    load_document_and_chunks_to_database(
        document=parsed_pdf.metadata.to_dict(),
        chunks=embedding_result.chunks,
    )

    LOGGER.info('Downloaded PDF to %s', pdf_path)
    LOGGER.info(
        'Ingested %d pages and %d chunks',
        parsed_pdf.metadata.page_count,
        len(embedding_result.chunks),
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
    documents_list: TextIO,
    tmp_folder: Path | None,
    timeout: float | None,
    verbose: bool | None,
) -> None:
    """Download and parse the PDFs described by DOCUMENT.

    DOCUMENTS_LIST is a JSON file path containing either one document object or an
    array of document objects. Use '-' to read JSON from stdin.
    """
    try:
        ingestion_documents = load_documents(documents_list)
        ingestion_settings = load_settings(
            tmp_folder=tmp_folder,
            timeout=timeout,
            verbose=verbose,
        )

    except (ValueError, ValidationError) as exc:
        raise click.ClickException(f'Invalid ingestion configuration:\n{exc}') from exc

    logging.basicConfig(
        level=logging.DEBUG if ingestion_settings.verbose else logging.INFO,
        format='%(levelname)s: %(message)s',
    )

    document_count = len(ingestion_documents)

    embedding_settings = EmbeddingSettings()
    embedder = FastEmbedder(
        model_name=embedding_settings.model_name,
        normalize=embedding_settings.normalize,
    )

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
            ingest_document(
                ingestion_document,
                ingestion_settings,
                embedder,
                embedding_settings.batch_size,
            )
        except (PdfDownloadError, PdfParseError, OSError) as exc:
            raise click.ClickException(
                f'Failed to ingest document {index}/{document_count} '
                f'({ingestion_document.title}, '
                f'{ingestion_document.pdf_url}): {exc}'
            ) from exc


if __name__ == '__main__':
    main()
