"""Deterministic end-to-end RAG checks using the demo LLM provider."""

from fastapi.testclient import TestClient

from ai_tour_guide.app.api import app
from ai_tour_guide.app.services.demo.questions import DEMO_LIMITATION_MESSAGE


def test_health_reports_a_populated_smoke_knowledge_base() -> None:
    response = TestClient(app).get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_chat_message_returns_a_prepared_answer_without_rag_sources() -> None:
    client = TestClient(app)
    start = client.post('/chat/start').json()
    response = client.post(
        '/chat/message',
        json={
            'session_id': start['session_id'],
            'expected_step_id': start['step_id'],
            'input_id': 'FREE_TEXT',
            'text': 'How can visitors travel from Rennes to Saint-Malo?',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == (
        'Visitors can take the regional train from Rennes to Saint-Malo; the '
        'journey usually takes about fifty minutes.'
    )
    assert payload['sources'] == []
    assert payload['trace']['final_status'] == 'answered'
    assert payload['trace']['actions'] == ['answer_from_prepared_questions']
    assert payload['trace']['evidence_sufficient'] is False


def test_chat_message_returns_a_demo_fallback_for_an_unsupported_question() -> None:
    client = TestClient(app)
    start = client.post('/chat/start').json()
    response = client.post(
        '/chat/message',
        json={
            'session_id': start['session_id'],
            'expected_step_id': start['step_id'],
            'input_id': 'FREE_TEXT',
            'text': 'Can you reserve a hotel in Saint-Malo tonight?',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'].startswith(DEMO_LIMITATION_MESSAGE)
    assert '\n\nTry asking: “' in payload['message']
    assert payload['sources'] == []
    assert payload['trace']['final_status'] == 'answered'
