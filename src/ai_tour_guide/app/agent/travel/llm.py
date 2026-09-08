"""Travel-agent adapter for the established LLM-backed RAG pipeline."""

import logging
from collections.abc import Callable

from sqlalchemy import Engine

from ai_tour_guide.app.agent.travel.contracts import (
    TravelAgentStatus,
    TravelTurnContext,
    TravelTurnResult,
    TravelTurnTrace,
)
from ai_tour_guide.app.llm.clients import LLMClient
from ai_tour_guide.app.services.rag.pipeline import answer_question_async
from ai_tour_guide.knowledge_base.retrieval.catalog import has_indexed_documents
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy

logger = logging.getLogger(__name__)


class LLMTravelAgent:
    """Answer travel questions through the existing source-grounded RAG pipeline."""

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        engine: Engine | None = None,
        strategy: SearchStrategy | None = None,
        knowledge_base_available: Callable[[], bool] | None = None,
        retrieval_enabled: bool = True,
    ) -> None:
        self._llm_client = llm_client
        self._engine = engine
        self._strategy = strategy
        self._knowledge_base_available = (
            knowledge_base_available
            if knowledge_base_available is not None
            else lambda: has_indexed_documents(engine)
        )
        self._retrieval_enabled = retrieval_enabled

    async def answer(
        self, question: str, context: TravelTurnContext
    ) -> TravelTurnResult:
        """Adapt the stable RAG result to the travel-agent contract."""
        logger.info(
            'llm_agent.started session_id=%s flow_step=%s retrieval_enabled=%s '
            'question=%r',
            context.session_id,
            context.flow_step.value,
            self._retrieval_enabled,
            question,
        )
        result = await answer_question_async(
            question,
            flow_step=context.flow_step,
            conversation_history=context.conversation_history,
            llm_client=self._llm_client,
            engine=self._engine,
            strategy=self._strategy,
            knowledge_base_available=self._knowledge_base_available,
            retrieval_enabled=self._retrieval_enabled,
        )
        queries = tuple(
            query
            for query in result.retrieval_metadata.get('tool_queries', [])
            if isinstance(query, str)
        )
        logger.info(
            'llm_agent.completed session_id=%s request_id=%s error=%s '
            'context_count=%s query_count=%s retrieval_status=%s',
            context.session_id,
            result.request_id,
            result.error.category.value if result.error is not None else None,
            len(result.contexts),
            len(queries),
            result.retrieval_metadata.get('retrieval_status'),
        )
        return TravelTurnResult(
            answer=result.answer,
            status=(
                TravelAgentStatus.FAILED
                if result.error is not None
                else TravelAgentStatus.ANSWERED
                if result.contexts
                or result.retrieval_metadata.get('retrieval_status')
                in {'disabled', 'not_requested'}
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
            metadata={
                'provider': result.llm_metadata.get('provider', ''),
                'evidence': result.to_dict().get('contexts', []),
            },
            persistence_payload=result.to_dict(),
            error_message=result.error.category.value if result.error else None,
        )


__all__ = ['LLMTravelAgent']
