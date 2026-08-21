"""Tests for scoped corpus lifecycle management."""

from pathlib import Path
from unittest.mock import patch

from ai_tour_guide.knowledge_base.corpus.context import corpus_context


@patch('ai_tour_guide.knowledge_base.corpus.context.clear_knowledge_base')
@patch('ai_tour_guide.knowledge_base.corpus.context.load_corpus')
def test_corpus_context_loads_before_yield_and_clears_after(
    load_corpus, clear_knowledge_base
) -> None:
    """Verify that a scoped corpus is loaded before work and cleared afterward."""
    root = Path('fixture-corpus')

    with corpus_context(root=root, schema_name='evaluation'):
        load_corpus.assert_called_once_with(root=root, schema_name='evaluation')
        clear_knowledge_base.assert_not_called()

    clear_knowledge_base.assert_called_once_with(schema_name='evaluation')


@patch('ai_tour_guide.knowledge_base.corpus.context.clear_knowledge_base')
@patch('ai_tour_guide.knowledge_base.corpus.context.load_corpus')
def test_corpus_context_can_preserve_loaded_rows(
    load_corpus, clear_knowledge_base
) -> None:
    """Verify that callers can retain loaded corpus rows after a scoped operation."""
    with corpus_context(clear_after=False):
        pass

    load_corpus.assert_called_once()
    clear_knowledge_base.assert_not_called()
