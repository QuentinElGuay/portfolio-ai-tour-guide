"""Shared constants describing the logical JSONL corpus format."""

from pathlib import Path

COPY_OPTIONS = "FORMAT CSV, DELIMITER E'\\x01', QUOTE E'\\x02'"
CORPUS_FILES = (
    'embedding_models.jsonl',
    'documents.jsonl',
    'document_chunks.jsonl',
)
DEFAULT_CORPUS_ROOT = Path('fixtures/corpus')

__all__ = ['COPY_OPTIONS', 'CORPUS_FILES', 'DEFAULT_CORPUS_ROOT']
