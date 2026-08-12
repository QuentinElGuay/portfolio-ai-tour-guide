from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from ai_tour_guide.agent.rag.models import GeneratedAnswer, LLMCitation
from ai_tour_guide.agent.rag.pipeline import answer_question
from ai_tour_guide.agent.responses import INSUFFICIENT_CONTEXT_ANSWER
from ai_tour_guide.knowledge_base.retrieval import (
    RetrievedChunk,
    ScoreKind,
    SourceMetadata,
)


def _retrieved() -> RetrievedChunk:
    chunk = SimpleNamespace(
        chunk_id='chunk-123',
        page_start=12,
        page_end=12,
        text='Opens at ten.',
        content_hash='hash',
    )
    return RetrievedChunk(
        chunk=chunk,
        rank=1,
        score=0.9,
        score_kind=ScoreKind.TEXT_RANK,
        source=SourceMetadata(
            document_id=7,
            chunk_id='chunk-123',
            title='Museum guide',
            source_url='https://example.com/museum',
            publisher='Board',
            publication_date=None,
            collection='guides',
            version='2026',
            section_path=('Museum',),
            page_start=12,
            page_end=12,
        ),
    )


@patch('ai_tour_guide.agent.rag.pipeline.retrieve')
def test_answer_question_retains_full_trace_and_validated_sources(
    retrieve: MagicMock,
) -> None:
    retrieve.return_value = [_retrieved()]
    client = MagicMock()
    client.answer_question = AsyncMock(
        return_value=GeneratedAnswer(
            'It opens at ten.',
            (LLMCitation('https://example.com/museum', '2026', 12, 12),),
        )
    )
    result = answer_question('When?', mode='text', k=3, client=client)
    assert result.answer == 'It opens at ten.'
    assert result.sources[0].pages == (12,)
    assert result.retrieved == (_retrieved(),)
    assert 'https://example.com/museum' in result.context
    assert result.to_dict()['retrieved'][0]['text'] == 'Opens at ten.'


@patch('ai_tour_guide.agent.rag.pipeline.retrieve', return_value=[])
def test_empty_retrieval_is_insufficient_context(retrieve: MagicMock) -> None:
    result = answer_question('Unknown', client=MagicMock())
    assert result.answer == INSUFFICIENT_CONTEXT_ANSWER
    assert result.context == ''
    assert result.messages == ()
