import asyncio
import json

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


def test_deterministic_travel_agent_answers_a_prepared_question_without_retrieval() -> (
    None
):
    agent = DeterministicTravelAgent(DeterministicQuestionsService())

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
    agent = DeterministicTravelAgent(DeterministicQuestionsService(dataset_path))

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
