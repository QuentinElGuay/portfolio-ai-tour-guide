"""Readers for user-supplied ingestion document definitions."""

import json
from pathlib import Path
from typing import TextIO

from ai_tour_guide.ingestion.pdf.parser import IngestionDocument


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
        raise TypeError(
            'The ingestion input must be a JSON object or an array of JSON objects'
        )

    documents: list[IngestionDocument] = []
    for index, values in enumerate(document_values, start=1):
        if not isinstance(values, dict):
            raise TypeError(f'Document {index} must be a JSON object')
        try:
            documents.append(IngestionDocument.from_dict(values))
        except (TypeError, ValueError) as exc:
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


def load_document(source: TextIO) -> IngestionDocument:
    """Load exactly one ingestion document from a JSON stream."""
    documents = load_documents(source)
    if len(documents) != 1:
        raise ValueError('This command accepts exactly one document')
    return documents[0]


def read_document(path: str | Path) -> IngestionDocument:
    """Load exactly one ingestion document from a JSON file."""
    with Path(path).open('r', encoding='utf-8') as source:
        return load_document(source)


__all__ = ['load_document', 'load_documents', 'read_document']
