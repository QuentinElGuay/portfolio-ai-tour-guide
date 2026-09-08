import asyncio
import json
from unittest.mock import MagicMock

import pytest

from ai_tour_guide.app.agent.flow import FlowStep
from ai_tour_guide.app.agent.travel.contracts import TravelTurnContext
from ai_tour_guide.app.agent.travel.deterministic import (
    DeterministicTravelAgent,
    create_deterministic_travel_agent,
)
from ai_tour_guide.app.llm.factory import create_llm_client
from ai_tour_guide.app.llm.settings import AgentsSettings, LLMProvider
from ai_tour_guide.app.services.demo.questions import (
    DEFAULT_DEMO_DATASET_PATH,
    DEMO_LIMITATION_MESSAGE,
    DeterministicQuestionsService,
)
from ai_tour_guide.knowledge_base.retrieval.tool import (
    RetrievalStatus,
    TourismEvidence,
    TourismSearchQuery,
    TourismSearchResult,
)
from ai_tour_guide.knowledge_base.search.models import ScoreKind


def _agent(
    questions: DeterministicQuestionsService,
    *,
    knowledge_base_available: bool,
    result: TourismSearchResult | None = None,
) -> tuple[DeterministicTravelAgent, MagicMock]:
    search = MagicMock(
        return_value=result
        or TourismSearchResult(
            status=RetrievalStatus.EMPTY,
            query=TourismSearchQuery('placeholder'),
        )
    )
    return (
        DeterministicTravelAgent(
            questions,
            knowledge_base_available=lambda: knowledge_base_available,
            search=search,
        ),
        search,
    )


def _evidence(*, score: float = 0.9) -> TourismEvidence:
    return TourismEvidence(
        text='Rennes is the capital of Brittany.\n\nBrest is a maritime city.',
        source_url='https://example.test/brittany-guide',
        title='Discover Brittany',
        version='2026',
        publisher='Tourism Board',
        collection='Guides',
        publication_date=None,
        pages=(8, 9),
        document_id=1,
        section_id='main-cities',
        section_path=('Guide', 'Main Cities'),
        rank=1,
        score=score,
        score_kind=ScoreKind.COSINE_SIMILARITY,
    )


def test_deterministic_travel_agent_uses_prepared_questions_when_the_kb_is_empty() -> (
    None
):
    agent, search = _agent(
        DeterministicQuestionsService(), knowledge_base_available=False
    )

    result = asyncio.run(
        agent.answer(
            'What is kouign-amann?',
            TravelTurnContext(session_id='session', flow_step=FlowStep.MAIN_MENU),
        )
    )

    assert result.answer == (
        'Kouign-amann is a rich, buttery Breton pastry known for its caramelised '
        'sugar crust.'
    )
    assert result.metadata['retrieval_status'] == 'empty_knowledge_base'
    search.assert_not_called()


def test_deterministic_demo_layer_bypasses_retrieval() -> None:
    availability = MagicMock(return_value=True)
    search = MagicMock()
    agent = DeterministicTravelAgent(
        DeterministicQuestionsService(),
        knowledge_base_available=availability,
        search=search,
        retrieval_enabled=False,
    )

    result = asyncio.run(
        agent.answer(
            'What is kouign-amann?',
            TravelTurnContext(session_id='session', flow_step=FlowStep.MAIN_MENU),
        )
    )

    assert result.answer.startswith('Kouign-amann is a rich, buttery Breton pastry')
    assert result.metadata['retrieval_status'] == 'demo'
    availability.assert_not_called()
    search.assert_not_called()


def test_deterministic_travel_agent_displays_retrieved_logical_contexts() -> None:
    evidence = _evidence()
    agent, search = _agent(
        DeterministicQuestionsService(),
        knowledge_base_available=True,
        result=TourismSearchResult(
            status=RetrievalStatus.SUCCESS,
            query=TourismSearchQuery('main cities'),
            evidence=(evidence,),
        ),
    )

    result = asyncio.run(
        agent.answer(
            'What are Brittany’s main cities?',
            TravelTurnContext(session_id='session', flow_step=FlowStep.MAIN_MENU),
        )
    )

    assert result.answer == (
        '🔎 1 relevant section found\n\n'
        '### 1. Main Cities\n\n'
        '**Discover Brittany · pages 8 and 9**\n\n'
        'Rennes is the capital of Brittany.\n\nBrest is a maritime city.'
    )
    assert result.trace.actions == (
        'search_knowledge_base',
        'display_retrieved_evidence',
    )
    assert result.trace.evidence_sufficient is True
    search.assert_called_once_with('What are Brittany’s main cities?')


def test_deterministic_travel_agent_displays_low_confidence_evidence() -> None:
    evidence = _evidence(score=0.4)
    agent, _ = _agent(
        DeterministicQuestionsService(),
        knowledge_base_available=True,
        result=TourismSearchResult(
            status=RetrievalStatus.LOW_CONFIDENCE,
            query=TourismSearchQuery('main cities'),
            low_confidence_evidence=(evidence,),
        ),
    )

    result = asyncio.run(
        agent.answer(
            'What are Brittany’s main cities?',
            TravelTurnContext(session_id='session', flow_step=FlowStep.MAIN_MENU),
        )
    )

    assert result.status.value == 'answered'
    assert 'Rennes is the capital of Brittany.' in result.answer
    assert result.metadata['retrieval_status'] == 'low_confidence'


def test_deterministic_travel_agent_reports_no_matching_sections() -> None:
    agent, _ = _agent(
        DeterministicQuestionsService(),
        knowledge_base_available=True,
        result=TourismSearchResult(
            status=RetrievalStatus.EMPTY,
            query=TourismSearchQuery('unknown place'),
        ),
    )

    result = asyncio.run(
        agent.answer(
            'Tell me about an unknown place',
            TravelTurnContext(session_id='session', flow_step=FlowStep.MAIN_MENU),
        )
    )

    assert result.status.value == 'refused'
    assert result.answer.startswith('I could not find relevant sections')


def test_deterministic_travel_agent_falls_back_when_retrieval_is_unavailable() -> None:
    availability = MagicMock(side_effect=RuntimeError('database unavailable'))
    search = MagicMock()
    agent = DeterministicTravelAgent(
        DeterministicQuestionsService(),
        knowledge_base_available=availability,
        search=search,
    )

    result = asyncio.run(
        agent.answer(
            'What is kouign-amann?',
            TravelTurnContext(session_id='session', flow_step=FlowStep.MAIN_MENU),
        )
    )

    assert result.answer.startswith('Kouign-amann is a rich, buttery Breton pastry')
    assert result.metadata['retrieval_status'] == 'unavailable'
    search.assert_not_called()


def test_deterministic_travel_agent_suggests_a_similar_prepared_question(
    tmp_path,
) -> None:
    dataset_path = tmp_path / 'demo.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'question': 'What can I do in Brittany?',
                'answer': 'Visit the coast.',
                'source': None,
            }
        )
        + '\n',
        encoding='utf-8',
    )
    agent, _ = _agent(
        DeterministicQuestionsService(dataset_path), knowledge_base_available=False
    )

    result = asyncio.run(
        agent.answer(
            'What activities can I do in Brittany?',
            TravelTurnContext(session_id='session', flow_step=FlowStep.MAIN_MENU),
        )
    )

    assert result.answer.startswith(DEMO_LIMITATION_MESSAGE)
    assert 'Did you mean: “What can I do in Brittany?”' in result.answer


def test_deterministic_travel_agent_uses_the_configured_dataset() -> None:
    agent = create_deterministic_travel_agent(
        AgentsSettings(
            llm_provider=LLMProvider.BAGUETTE_LLM,
            model='mini-croissant-1.0',
        )
    )

    assert agent.dataset_path == DEFAULT_DEMO_DATASET_PATH


def test_rag_client_factory_rejects_the_demo_provider() -> None:
    with pytest.raises(ValueError, match='served by DeterministicTravelAgent'):
        create_llm_client(
            AgentsSettings(
                llm_provider=LLMProvider.BAGUETTE_LLM,
                model='mini-croissant-1.0',
            )
        )
