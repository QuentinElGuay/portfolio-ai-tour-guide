from unittest.mock import MagicMock, patch

from ai_tour_guide.agent.api import AskRequest, ask
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGResult, SourceReference
from ai_tour_guide.knowledge_base.retrieval import SearchMode


@patch('ai_tour_guide.agent.api.answer_question')
def test_ask_returns_only_normalized_sources(answer_question: MagicMock) -> None:
    answer_question.return_value = RAGResult(
        question='What?',
        mode=SearchMode.VECTOR,
        k=5,
        context='',
        messages=(),
        generated=GeneratedAnswer('Visit.'),
        sources=(
            SourceReference(
                'https://example.com/museum',
                '2026',
                'Museum guide',
                'Board',
                'Guides',
                None,
                (4, 5),
            ),
        ),
    )
    response = ask(AskRequest(question=' What? ')).model_dump(mode='json')
    assert response == {
        'schema_version': 1,
        'answer': 'Visit.',
        'sources': [
            {
                'source_url': 'https://example.com/museum',
                'version': '2026',
                'title': 'Museum guide',
                'publisher': 'Board',
                'collection': 'Guides',
                'publication_date': None,
                'pages': [4, 5],
            }
        ],
    }
