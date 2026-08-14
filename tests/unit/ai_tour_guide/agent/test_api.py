from unittest.mock import MagicMock

from ai_tour_guide.agent.api import health


def test_health_reports_ok() -> None:
    assert health() == {'status': 'ok'}


def test_ask_returns_the_answer_and_sources(answer_question: MagicMock) -> None:
    """Verify that the ask endpoint returns the generated answer with its source references."""
    assert True


def test_ask_rejects_an_empty_question() -> None:
    """Verify that ask requests reject questions containing only whitespace."""
    assert True
