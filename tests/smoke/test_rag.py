"""Deterministic end-to-end RAG checks using the demo LLM provider."""

from fastapi.testclient import TestClient

from ai_tour_guide.app.agent.demo_questions import DEMO_LIMITATION_MESSAGE
from ai_tour_guide.app.api import app


def test_health_reports_a_populated_smoke_knowledge_base() -> None:
    response = TestClient(app).get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_chat_message_returns_a_golden_answer_with_validated_source_pages() -> None:
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
    assert len(payload['sources']) == 1
    source = payload['sources'][0]
    assert source['source_url'] == 'https://smoke.test/brittany-weekend-notes.pdf'
    assert source['version'] is None
    assert source['pages']
    assert all(isinstance(page, int) and page > 0 for page in source['pages'])
    assert payload['trace']['final_status'] == 'answered'
    assert payload['trace']['evidence_sufficient'] is True


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
