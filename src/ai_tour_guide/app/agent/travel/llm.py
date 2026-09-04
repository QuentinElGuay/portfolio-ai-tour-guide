"""Travel-agent adapter for the established LLM-backed RAG pipeline."""

from sqlalchemy import Engine

from ai_tour_guide.app.agent.travel.contracts import (
    TravelAgentStatus,
    TravelTurnContext,
    TravelTurnResult,
    TravelTurnTrace,
)
from ai_tour_guide.app.llm.clients import LLMClient
from ai_tour_guide.app.services.rag.pipeline import answer_question_async
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy


class LLMTravelAgent:
    """Answer travel questions through the existing source-grounded RAG pipeline."""

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        engine: Engine | None = None,
        strategy: SearchStrategy | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._engine = engine
        self._strategy = strategy

    async def answer(
        self, question: str, context: TravelTurnContext
    ) -> TravelTurnResult:
        """Adapt the stable RAG result to the travel-agent contract."""
        result = await answer_question_async(
            question,
            flow_step=context.flow_step,
            llm_client=self._llm_client,
            engine=self._engine,
            strategy=self._strategy,
        )
        queries = tuple(
            query
            for query in result.retrieval_metadata.get('tool_queries', [])
            if isinstance(query, str)
        )
        return TravelTurnResult(
            answer=result.answer,
            status=(
                TravelAgentStatus.FAILED
                if result.error is not None
                else TravelAgentStatus.ANSWERED
                if result.contexts
                else TravelAgentStatus.REFUSED
            ),
            request_id=result.request_id,
            sources=tuple(source.to_dict() for source in result.sources),
            trace=TravelTurnTrace(
                intent='travel_question',
                actions=tuple(
                    'search_knowledge_base' if index == 0 else 'reformulate_search'
                    for index in range(len(queries))
                )
                + (('answer_from_context',) if result.contexts else ('refuse',)),
                tool_inputs=queries,
                evidence_sufficient=bool(result.contexts),
            ),
            metadata={'provider': result.llm_metadata.get('provider', '')},
            persistence_payload=result.to_dict(),
            error_message=result.error.category.value if result.error else None,
        )


__all__ = ['LLMTravelAgent']
