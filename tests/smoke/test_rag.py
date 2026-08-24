"""Deterministic end-to-end RAG checks using the fixture LLM provider."""

from fastapi.testclient import TestClient

from ai_tour_guide.agent.api import app
from ai_tour_guide.agent.responses import INSUFFICIENT_CONTEXT_ANSWER


def test_health_reports_a_populated_smoke_knowledge_base() -> None:
    response = TestClient(app).get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_ask_returns_a_golden_answer_with_validated_source_pages() -> None:
    response = TestClient(app).post(
        '/ask',
        json={'question': 'How can visitors travel from Rennes to Saint-Malo?'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['answer'] == (
        'Visitors can take the regional train from Rennes to Saint-Malo; the '
        'journey usually takes about fifty minutes.'
    )
    assert len(payload['sources']) == 1
    source = payload['sources'][0]
    assert source['source_url'] == 'https://smoke.test/brittany-weekend-notes.pdf'
    assert source['version'] is None
    assert source['pages']
    assert all(isinstance(page, int) and page > 0 for page in source['pages'])


def test_ask_refuses_an_unsupported_golden_question() -> None:
    response = TestClient(app).post(
        '/ask', json={'question': 'Can you reserve a hotel in Saint-Malo tonight?'}
    )

    assert response.status_code == 200
    assert response.json()['answer'] == INSUFFICIENT_CONTEXT_ANSWER
    assert response.json()['sources'] == []
