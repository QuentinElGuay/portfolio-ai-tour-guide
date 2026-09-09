"""Tests for the RAG evaluation entry point."""

from evaluation.rag import run


def test_rag_runner_imports() -> None:
    """Keep the command-line evaluation runner importable."""
    assert run.LLMProvider is not None
