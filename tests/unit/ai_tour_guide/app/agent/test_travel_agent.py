from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest

from ai_tour_guide.app.agent.rag.models import GeneratedAnswer
from ai_tour_guide.app.agent.rag.tools import (
    RetrievalStatus,
    TourismEvidence,
    TourismSearchQuery,
    TourismSearchResult,
)
from ai_tour_guide.app.agent.responses import INSUFFICIENT_CONTEXT_ANSWER
from ai_tour_guide.app.agent.travel_agent import (
    TravelAgent,
    TravelAgentAction,
    TravelAgentStatus,
    build_travel_agent_graph,
)
from ai_tour_guide.knowledge_base.search.models import ScoreKind


def _evidence() -> TourismEvidence:
    return TourismEvidence(
        text='Take the train.',
        source_url='https://example.test/guide',
        title='Brittany Guide',
        version='2026',
        publisher=None,
        collection=None,
        publication_date=None,
        pages=(4,),
        document_id=1,
        section_id='transport',
        section_path=('Transport',),
        rank=1,
        score=0.9,
        score_kind=ScoreKind.TEXT_RANK,
    )


def _result(
    status: RetrievalStatus, evidence: tuple[TourismEvidence, ...] = ()
) -> TourismSearchResult:
    return TourismSearchResult(status, TourismSearchQuery('train'), evidence=evidence)


@pytest.mark.anyio
async def test_travel_agent_answers_with_injected_search_and_llm() -> None:
    llm = MagicMock()
    llm.choose_search_query = AsyncMock(return_value='train travel')
    llm.answer_question = AsyncMock(
        return_value=GeneratedAnswer(answer='Take the train.')
    )
    search = MagicMock(return_value=_result(RetrievalStatus.SUCCESS, (_evidence(),)))

    result = await TravelAgent(llm, search_tool=search).answer('How do I travel?')

    assert result.status is TravelAgentStatus.ANSWERED
    assert result.answer == 'Take the train.'
    assert result.trace.actions == (
        TravelAgentAction.SEARCH_KNOWLEDGE_BASE,
        TravelAgentAction.ANSWER_FROM_CONTEXT,
    )
    assert result.trace.tool_call_count == 1
    search.assert_called_once_with(TourismSearchQuery('train travel'))


@pytest.mark.anyio
async def test_travel_agent_refuses_without_a_query_or_evidence() -> None:
    llm = MagicMock()
    llm.choose_search_query = AsyncMock(return_value='train')
    search = MagicMock(return_value=_result(RetrievalStatus.EMPTY))

    result = await TravelAgent(llm, search_tool=search, max_search_retries=0).answer(
        'Question?'
    )

    assert result.status is TravelAgentStatus.NO_EVIDENCE
    assert result.answer == INSUFFICIENT_CONTEXT_ANSWER
    assert result.trace.actions[-1] is TravelAgentAction.REFUSE
    llm.answer_question.assert_not_called()


@pytest.mark.anyio
async def test_travel_agent_reports_retrieval_errors_without_provider_details() -> None:
    llm = MagicMock()
    llm.choose_search_query = AsyncMock(return_value='train')
    search = MagicMock(
        return_value=TourismSearchResult(
            RetrievalStatus.ERROR,
            TourismSearchQuery('train'),
            error=MagicMock(error_type='DatabaseError', message='down'),
        )
    )

    result = await TravelAgent(llm, search_tool=search).answer('Question?')

    assert result.status is TravelAgentStatus.RETRIEVAL_ERROR
    assert result.trace.final_status is TravelAgentStatus.RETRIEVAL_ERROR
    assert result.trace.actions[-1] is TravelAgentAction.REFUSE


@pytest.mark.anyio
async def test_travel_agent_graph_returns_structured_turn_state() -> None:
    llm = MagicMock()
    llm.choose_search_query = AsyncMock(return_value='train travel')
    llm.answer_question = AsyncMock(
        return_value=GeneratedAnswer(answer='Take the train.')
    )
    search = MagicMock(return_value=_result(RetrievalStatus.SUCCESS, (_evidence(),)))

    graph = build_travel_agent_graph(TravelAgent(llm, search_tool=search))
    with anyio.fail_after(5):
        state = await graph.ainvoke({'question': 'How do I travel?'})

    assert state['answer'] == 'Take the train.'
    assert state['final_status'] is TravelAgentStatus.ANSWERED
    assert state['tool_calls'] == 1
