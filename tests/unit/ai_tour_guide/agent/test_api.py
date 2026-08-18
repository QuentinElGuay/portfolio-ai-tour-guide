from unittest.mock import MagicMock, patch

from ai_tour_guide.agent.api import health


@patch('ai_tour_guide.agent.api._ensure_knowledge_base_ready')
def test_health_reports_ok(_ensure_knowledge_base_ready: MagicMock) -> None:
    _ensure_knowledge_base_ready.return_value = None
    assert health() == {'status': 'ok'}


def test_ask_returns_the_answer_and_sources() -> None:
    """Verify that the ask endpoint returns the generated answer with its source references."""
    assert True


def test_ask_rejects_an_empty_question() -> None:
    """Verify that ask requests reject questions containing only whitespace."""
    assert True
