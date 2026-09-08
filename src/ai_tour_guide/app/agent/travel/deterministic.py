"""Deterministic travel agent backed by retrieval or prepared questions."""

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.app.agent.travel.contracts import (
    TravelAgentStatus,
    TravelTurnContext,
    TravelTurnResult,
    TravelTurnTrace,
)
from ai_tour_guide.app.agent.travel.retrieval_formatting import (
    format_retrieval_evidence,
)
from ai_tour_guide.app.llm.settings import AgentsSettings
from ai_tour_guide.app.services.demo.questions import (
    DEFAULT_DEMO_DATASET_PATH,
    DemoResponse,
    DeterministicQuestionsService,
)
from ai_tour_guide.knowledge_base.retrieval.catalog import has_indexed_documents
from ai_tour_guide.knowledge_base.retrieval.tool import (
    RetrievalStatus,
    TourismSearchResult,
    search_tourism_knowledge_base,
)
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy

type KnowledgeBaseAvailability = Callable[[], bool]
type TourismSearch = Callable[[str], TourismSearchResult]


class DeterministicTravelAgent:
    """Return retrieved evidence, with prepared questions as the KB fallback."""

    def __init__(
        self,
        questions: DeterministicQuestionsService,
        *,
        knowledge_base_available: KnowledgeBaseAvailability,
        search: TourismSearch,
        retrieval_enabled: bool = True,
    ) -> None:
        self._questions = questions
        self._knowledge_base_available = knowledge_base_available
        self._search = search
        self._retrieval_enabled = retrieval_enabled

    @property
    def dataset_path(self) -> Path:
        """Return the dataset used by this demo agent."""
        return self._questions.dataset_path

    async def answer(
        self, question: str, context: TravelTurnContext
    ) -> TravelTurnResult:
        """Return evidence when possible, or a prepared answer without a KB."""
        del context
        if not self._retrieval_enabled:
            return self._prepared_answer(question, retrieval_status='demo')
        try:
            indexed_documents_available = self._knowledge_base_available()
        except OSError, RuntimeError, SQLAlchemyError:
            return self._prepared_answer(question, retrieval_status='unavailable')

        if not indexed_documents_available:
            return self._prepared_answer(
                question, retrieval_status='empty_knowledge_base'
            )

        try:
            result = self._search(question)
        except OSError, RuntimeError, SQLAlchemyError:
            return self._prepared_answer(question, retrieval_status='unavailable')
        if result.status is RetrievalStatus.ERROR:
            return self._prepared_answer(question, retrieval_status='unavailable')
        if result.status is RetrievalStatus.EMPTY:
            return TravelTurnResult(
                answer=format_retrieval_evidence(()),
                status=TravelAgentStatus.REFUSED,
                trace=TravelTurnTrace(
                    intent='travel_question',
                    actions=('search_knowledge_base', 'report_no_relevant_sections'),
                    tool_inputs=(question,),
                ),
                metadata={'provider': 'baguette-llm', 'retrieval_status': 'empty'},
            )
        evidence = result.all_evidence
        return TravelTurnResult(
            answer=format_retrieval_evidence(evidence),
            status=TravelAgentStatus.ANSWERED,
            trace=TravelTurnTrace(
                intent='travel_question',
                actions=('search_knowledge_base', 'display_retrieved_evidence'),
                tool_inputs=(question,),
                evidence_sufficient=bool(evidence),
            ),
            metadata={
                'provider': 'baguette-llm',
                'retrieval_status': result.status.value,
                'retrieved_context_count': len(evidence),
                'evidence': [item.to_dict() for item in evidence],
            },
        )

    def _prepared_answer(
        self, question: str, *, retrieval_status: str
    ) -> TravelTurnResult:
        """Return a prepared response when the knowledge base cannot be used."""
        response: DemoResponse = self._questions.answer(question)
        return TravelTurnResult(
            answer=response.text,
            status=TravelAgentStatus.ANSWERED,
            trace=TravelTurnTrace(
                intent='travel_question',
                actions=('answer_from_prepared_questions',),
            ),
            metadata={
                'provider': 'baguette-llm',
                'dataset': str(self.dataset_path),
                'retrieval_status': retrieval_status,
            },
        )


def create_deterministic_travel_agent(
    settings: AgentsSettings,
    *,
    engine: Engine | None = None,
    strategy: SearchStrategy | None = None,
    retrieval_enabled: bool = True,
) -> DeterministicTravelAgent:
    """Create the retrieval-backed deterministic agent from configuration."""
    return DeterministicTravelAgent(
        DeterministicQuestionsService(
            settings.demo_dataset_path or DEFAULT_DEMO_DATASET_PATH,
            close_question_distance=settings.close_question_distance,
            similar_question_distance=settings.similar_question_distance,
        ),
        knowledge_base_available=lambda: has_indexed_documents(engine),
        search=lambda question: search_tourism_knowledge_base(
            question, engine=engine, strategy=strategy
        ),
        retrieval_enabled=retrieval_enabled,
    )


__all__ = ['DeterministicTravelAgent', 'create_deterministic_travel_agent']
