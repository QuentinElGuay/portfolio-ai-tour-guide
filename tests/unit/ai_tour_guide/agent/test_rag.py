import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('EMBEDDING_DIMENSIONS', '384')
os.environ.setdefault('EMBEDDING_MODEL_NAME', 'test-model')

from ai_tour_guide.agent.rag.models import RAGResult
from ai_tour_guide.agent.rag.pipeline import (
    INSUFFICIENT_CONTEXT_ANSWER,
    answer_question,
)
from ai_tour_guide.agent.rag.prompting import build_context
from ai_tour_guide.knowledge_base.retrieval import (
    RetrievedChunk,
    ScoreKind,
    SourceMetadata,
)


def _chunk():
    return SimpleNamespace(
        chunk_id='chunk-123',
        page_start=12,
        page_end=12,
        text='The museum opens at ten.',
    )


@patch('ai_tour_guide.agent.rag.pipeline.create_backend')
@patch('ai_tour_guide.agent.rag.pipeline.retrieve')
def test_answer_question_retrieves_context_and_returns_sources(
    retrieve: MagicMock,
    create_backend: MagicMock,
) -> None:
    chunk = _chunk()
    retrieve.return_value = [
        RetrievedChunk(
            chunk=chunk,
            rank=1,
            score=0.9,
            score_kind=ScoreKind.TEXT_RANK,
            source=SourceMetadata(
                document_id=7,
                chunk_id='chunk-123',
                title='A museum guide',
                source_url='https://example.com/museum',
                publisher=None,
                publication_date=None,
                collection=None,
                version=None,
                section_path=('Museum',),
                page_start=12,
                page_end=12,
            ),
        )
    ]
    backend = MagicMock()
    backend.generate = AsyncMock(return_value='It opens at ten.')
    create_backend.return_value = backend

    result = answer_question('When does it open?', mode='text', k=3)

    assert result == RAGResult(
        answer='It opens at ten.',
        retrieved=[
            RetrievedChunk(
                chunk=chunk,
                rank=1,
                score=0.9,
                score_kind=ScoreKind.TEXT_RANK,
                source=SourceMetadata(
                    document_id=7,
                    chunk_id='chunk-123',
                    title='A museum guide',
                    source_url='https://example.com/museum',
                    publisher=None,
                    publication_date=None,
                    collection=None,
                    version=None,
                    section_path=('Museum',),
                    page_start=12,
                    page_end=12,
                ),
            )
        ],
    )
    retrieve.assert_called_once_with('When does it open?', mode='text', k=3)
    messages = backend.generate.call_args.args[0]
    assert 'chunk-123' in messages[1]['content']
    assert 'The museum opens at ten.' in messages[1]['content']
    assert 'When does it open?' in messages[1]['content']


@patch('ai_tour_guide.agent.rag.pipeline.create_backend')
@patch('ai_tour_guide.agent.rag.pipeline.retrieve', return_value=[])
def test_answer_question_handles_empty_retrieval(
    retrieve: MagicMock,
    create_backend: MagicMock,
) -> None:
    result = answer_question('Unknown question')

    assert result.answer == INSUFFICIENT_CONTEXT_ANSWER
    assert result.chunks == []
    create_backend.assert_not_called()


def test_build_context_preserves_source_identity_and_pages() -> None:
    assert build_context([_chunk()]) == (
        '[Source: chunk-123, page 12]\nThe museum opens at ten.'
    )
