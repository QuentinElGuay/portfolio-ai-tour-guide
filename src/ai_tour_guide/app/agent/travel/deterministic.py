"""Deterministic travel agent backed by prepared questions."""

from pathlib import Path

from ai_tour_guide.app.agent.travel.contracts import (
    TravelAgentStatus,
    TravelTurnContext,
    TravelTurnResult,
    TravelTurnTrace,
)
from ai_tour_guide.app.llm.settings import AgentsSettings
from ai_tour_guide.app.services.demo.questions import (
    DEFAULT_DEMO_DATASET_PATH,
    DemoResponse,
    DeterministicQuestionsService,
)


class DeterministicTravelAgent:
    """Answer demo questions without calling the retrieval workflow."""

    def __init__(self, questions: DeterministicQuestionsService) -> None:
        self._questions = questions

    @property
    def dataset_path(self) -> Path:
        """Return the dataset used by this demo agent."""
        return self._questions.dataset_path

    async def answer(
        self, question: str, context: TravelTurnContext
    ) -> TravelTurnResult:
        """Return the deterministic answer for ``question``."""
        del context
        response: DemoResponse = self._questions.answer(question)
        return TravelTurnResult(
            answer=response.text,
            status=TravelAgentStatus.ANSWERED,
            trace=TravelTurnTrace(
                intent='travel_question',
                actions=('answer_from_prepared_questions',),
            ),
            metadata={'provider': 'baguette-llm', 'dataset': str(self.dataset_path)},
        )


def create_deterministic_travel_agent(
    settings: AgentsSettings,
) -> DeterministicTravelAgent:
    """Create the demo-only agent from application configuration."""
    return DeterministicTravelAgent(
        DeterministicQuestionsService(
            settings.demo_dataset_path or DEFAULT_DEMO_DATASET_PATH,
            close_question_distance=settings.close_question_distance,
            similar_question_distance=settings.similar_question_distance,
        )
    )


__all__ = ['DeterministicTravelAgent', 'create_deterministic_travel_agent']
