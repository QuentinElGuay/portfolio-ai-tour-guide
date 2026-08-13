"""Shared pytest fixtures for knowledge-base tests."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager

import pytest

from ai_tour_guide.knowledge_base.corpus import clear_knowledge_base, corpus_context


@pytest.fixture
def empty_knowledge_base() -> Iterator[None]:
    """Provide an empty knowledge base and clean it again after the test."""
    # TODO: Add a hard guard for an isolated test database before enabling this
    # fixture in CI or local test runs.
    clear_knowledge_base()
    try:
        yield
    finally:
        clear_knowledge_base()


@pytest.fixture
def corpus_knowledge_base() -> Callable[[int], AbstractContextManager[None]]:
    """Return a factory for loading the current corpus in a test context.

    Example::

        def test_search(corpus_knowledge_base):
            with corpus_knowledge_base(1):
                ...
    """
    # TODO: Add a hard guard for an isolated test database before enabling this
    # fixture in CI or local test runs.
    return lambda: corpus_context()
