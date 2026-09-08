"""Focused confidence-policy tests independent of LangGraph execution."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ai_tour_guide.app.agent.responses import LOW_CONFIDENCE_RETRIEVAL_ANSWER
from ai_tour_guide.app.services.rag.models import GeneratedAnswer
from ai_tour_guide.app.services.rag.pipeline import answer_question_async
from ai_tour_guide.app.services.rag.workflow import run_agent_workflow


@patch(
    'ai_tour_guide.app.services.rag.pipeline.run_agent_workflow',
    new_callable=AsyncMock,
)
def test_pipeline_refuses_low_confidence_evidence_without_generation(
    run_agent_workflow: AsyncMock,
) -> None:
    """Verify low-score retrieval is never passed to the LLM generation stage."""
    run_agent_workflow.return_value = {
        'question': 'Question',
        'option_id': None,
        'flow_step': 'main_menu',
        'input_type': 'free_text',
        'queries': ['Question'],
        'contexts': (),
        'next_query': None,
        'retrieval_status': 'low_confidence',
        'low_confidence_retrieval': True,
    }

    result = asyncio.run(answer_question_async('Question', llm_client=MagicMock()))

    assert result.answer == LOW_CONFIDENCE_RETRIEVAL_ANSWER
    assert result.contexts == ()
    assert result.retrieval_metadata['retrieval_status'] == 'low_confidence'


def test_empty_knowledge_base_uses_limited_meta_conversation() -> None:
    """Verify the LLM is constrained to meta conversation when no guides exist."""
    client = MagicMock()
    client.choose_search_query = AsyncMock()
    client.answer_question = AsyncMock(
        return_value=GeneratedAnswer('I am Petit Guide.')
    )

    state = asyncio.run(
        run_agent_workflow(
            'What can you do?',
            client,
            knowledge_base_available=lambda: False,
        )
    )

    assert state['contexts'] == ()
    assert state['queries'] == []
    generated = state.get('generated')
    messages = state.get('messages')
    assert generated is not None
    assert messages is not None
    assert generated.answer == 'I am Petit Guide.'
    client.choose_search_query.assert_not_awaited()
    client.answer_question.assert_awaited_once_with(messages)


def test_disabled_retrieval_uses_limited_meta_conversation() -> None:
    client = MagicMock()
    client.choose_search_query = AsyncMock()
    client.answer_question = AsyncMock(
        return_value=GeneratedAnswer('I am Petit Guide.')
    )

    state = asyncio.run(
        run_agent_workflow('What can you do?', client, retrieval_enabled=False)
    )

    assert state['contexts'] == ()
    assert state['queries'] == []
    assert state.get('retrieval_status') == 'disabled'
    client.choose_search_query.assert_not_awaited()
    client.answer_question.assert_awaited_once()
