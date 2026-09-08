"""Deterministic end-to-end RAG checks using the demo LLM provider."""

from fastapi.testclient import TestClient

from ai_tour_guide.app.api import app


def test_health_reports_a_populated_smoke_knowledge_base() -> None:
    response = TestClient(app).get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_chat_message_returns_formatted_retrieval_evidence() -> None:
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
    assert payload['message'].startswith('🔎 2 relevant sections found')
    assert 'marked path.' in payload['message']
    assert payload['sources'] == []
    assert len(payload['evidence']) == 2
    assert payload['trace']['final_status'] == 'answered'
    assert payload['trace']['actions'] == [
        'search_knowledge_base',
        'display_retrieved_evidence',
    ]
    assert payload['trace']['evidence_sufficient'] is True


def test_chat_message_displays_low_confidence_retrieval_evidence() -> None:
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
    assert payload['message'].startswith('🔎 2 relevant sections found')
    assert payload['sources'] == []
    assert len(payload['evidence']) == 2
    assert payload['trace']['final_status'] == 'answered'
    assert payload['trace']['actions'] == [
        'search_knowledge_base',
        'display_retrieved_evidence',
    ]
