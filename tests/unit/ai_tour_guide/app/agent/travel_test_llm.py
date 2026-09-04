from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_tour_guide.app.agent.flow import FlowStep
from ai_tour_guide.app.agent.travel.contracts import (
    TravelAgentStatus,
    TravelTurnContext,
)
from ai_tour_guide.app.agent.travel.llm import LLMTravelAgent
from ai_tour_guide.app.services.rag.models import GeneratedAnswer, RAGResult
from ai_tour_guide.knowledge_base.search import SearchMode


@patch(
    'ai_tour_guide.app.agent.travel.llm.answer_question_async',
    new_callable=AsyncMock,
)
@pytest.mark.anyio
async def test_llm_travel_agent_adapts_the_existing_rag_pipeline(
    answer_question_async: AsyncMock,
) -> None:
    answer_question_async.return_value = RAGResult(
        question='What should I visit?',
        mode=SearchMode.HYBRID,
        k=5,
        messages=(),
        generated=GeneratedAnswer('Visit Brittany.'),
        retrieval_metadata={'tool_queries': ['Brittany']},
    )

    result = await LLMTravelAgent(MagicMock()).answer(
        'What should I visit?',
        TravelTurnContext(session_id='session', flow_step=FlowStep.MAIN_MENU),
    )

    assert result.answer == 'Visit Brittany.'
    assert result.status is TravelAgentStatus.REFUSED
    assert result.trace.tool_inputs == ('Brittany',)
    answer_question_async.assert_awaited_once()
