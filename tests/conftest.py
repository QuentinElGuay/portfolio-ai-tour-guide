"""Shared pytest fixtures for knowledge-base tests."""

from __future__ import annotations

from collections.abc import Callable, ContextManager, Iterator

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
def corpus_knowledge_base() -> Callable[[int], ContextManager[None]]:
    """Return a factory for loading any versioned corpus in a test context.

    Example::

        def test_search(corpus_knowledge_base):
            with corpus_knowledge_base(1):
                ...
    """
    # TODO: Add a hard guard for an isolated test database before enabling this
    # fixture in CI or local test runs.
    return lambda version: corpus_context(version)
