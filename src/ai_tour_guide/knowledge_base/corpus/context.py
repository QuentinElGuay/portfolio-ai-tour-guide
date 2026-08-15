"""Scoped corpus lifecycle helper for tests and evaluations."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .format import DEFAULT_CORPUS_ROOT
from .restore import clear_knowledge_base, load_corpus


@contextmanager
def corpus_context(
    *,
    root: Path = DEFAULT_CORPUS_ROOT,
    clear_after: bool = True,
    schema_name: str = 'public',
) -> Iterator[None]:
    """Load one corpus for a scoped operation and optionally clear its rows on exit."""
    load_corpus(root=root, schema_name=schema_name)
    try:
        yield
    finally:
        if clear_after:
            clear_knowledge_base(schema_name=schema_name)


__all__ = ['corpus_context']
