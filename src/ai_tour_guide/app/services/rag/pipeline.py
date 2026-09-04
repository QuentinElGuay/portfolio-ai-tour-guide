"""Application orchestration for retrieval-augmented answers."""

import asyncio
import logging
from collections.abc import Mapping
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.app.agent.flow import (
    DEFAULT_FLOW_STEP,
    FlowStep,
    flow_step_for_option,
    input_type_for_option,
)
from ai_tour_guide.app.agent.responses import (
    INSUFFICIENT_CONTEXT_ANSWER,
)
from ai_tour_guide.app.chat.navigation import normalize_option_id
from ai_tour_guide.app.llm.clients import (
    GenerationError,
    LLMClient,
)
from ai_tour_guide.app.llm.factory import create_llm_client
from ai_tour_guide.app.llm.settings import AgentsSettings
from ai_tour_guide.app.services.rag.models import (
    GeneratedAnswer,
    RAGError,
    RAGErrorCategory,
    RAGResult,
)
from ai_tour_guide.app.services.rag.prompting import build_messages
from ai_tour_guide.app.services.rag.sources import validate_citations
from ai_tour_guide.app.services.rag.workflow import run_agent_workflow
from ai_tour_guide.knowledge_base.search import DEFAULT_SEARCH_MODE, SearchMode
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy

logger = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """An expected knowledge-base operational failure."""


def _error(stage: str, exc: Exception, category: RAGErrorCategory) -> RAGError:
    logger.exception('%s failed', stage)
    return RAGError(
        category=category, stage=stage, type=type(exc).__name__, message=str(exc)
    )


def _elapsed_ms(started: float) -> int:
    """Return elapsed time in milliseconds using the RAG result's integer type."""
    return round((perf_counter() - started) * 1000)


def _interaction_metadata(
    state: Mapping[str, object], mode: SearchMode, flow_step: FlowStep
) -> dict[str, object]:
    """Expose backend-owned interaction labels in the persisted RAG trace."""
    return {
        'mode': mode.value,
        'tool_queries': state.get('queries', []),
        'option_id': state.get('option_id'),
        'flow_step': state.get('flow_step', flow_step.value),
        'input_type': state.get('input_type', 'free_text'),
    }


def _fallback_interaction_metadata(
    option_id: str | None, flow_step: FlowStep, mode: SearchMode
) -> dict[str, object]:
    """Build interaction labels when the graph failed before returning state."""
    return {
        'mode': mode.value,
        'tool_queries': [],
        'option_id': option_id,
        'flow_step': flow_step_for_option(option_id, flow_step).value,
        'input_type': input_type_for_option(option_id),
    }


async def answer_question_async(
    question: str,
    *,
    option_id: str | None = None,
    flow_step: FlowStep = DEFAULT_FLOW_STEP,
    mode: SearchMode = DEFAULT_SEARCH_MODE,
    k: int = 5,
    llm_client: LLMClient,
    engine: Engine | None = None,
    strategy: SearchStrategy | None = None,
    request_id: UUID | None = None,
) -> RAGResult:
    """Retrieve evidence, generate a cited answer, and retain its full trace."""
    started = perf_counter()
    selected_request_id = request_id or uuid4()
    selected_mode = SearchMode(mode)
    option_id = normalize_option_id(option_id)

    return await _answer_with_agent(
        question,
        option_id=option_id,
        flow_step=flow_step,
        mode=selected_mode,
        k=k,
        llm_client=llm_client,
        engine=engine,
        strategy=strategy,
        request_id=selected_request_id,
        started=started,
    )


async def _answer_with_agent(
    question: str,
    *,
    option_id: str | None,
    flow_step: FlowStep,
    mode: SearchMode,
    k: int,
    llm_client: LLMClient,
    engine: Engine | None,
    strategy: SearchStrategy | None,
    request_id: UUID,
    started: float,
) -> RAGResult:
    """Adapt the bounded LangGraph state to the stable RAG result contract."""
    retrieval_started = perf_counter()
    try:
        state = await run_agent_workflow(
            question,
            llm_client,
            option_id=option_id,
            flow_step=flow_step,
            engine=engine,
            strategy=strategy,
        )
    except (GenerationError, OSError, SQLAlchemyError) as exc:
        return RAGResult(
            question=question,
            request_id=request_id,
            mode=mode,
            k=k,
            messages=(),
            generated=GeneratedAnswer(''),
            error=_error(
                'agent',
                exc,
                RAGErrorCategory.EXTERNAL_SERVICE
                if isinstance(exc, GenerationError)
                else RAGErrorCategory.INTERNAL_SERVICE,
            ),
            total_latency_ms=_elapsed_ms(started),
            retrieval_metadata=_fallback_interaction_metadata(
                option_id, flow_step, mode
            ),
        )
    retrieval_latency = _elapsed_ms(retrieval_started)
    contexts = state['contexts']
    if 'retrieval_error' in state:
        exc = state['retrieval_error']
        return RAGResult(
            question=question,
            request_id=request_id,
            mode=mode,
            k=k,
            messages=(),
            generated=GeneratedAnswer(''),
            error=_error('retrieval', exc, RAGErrorCategory.INTERNAL_SERVICE),
            retrieval_latency_ms=retrieval_latency,
            total_latency_ms=_elapsed_ms(started),
            retrieval_metadata=_fallback_interaction_metadata(
                option_id, flow_step, mode
            ),
        )
    generated = state.get('generated')
    if not contexts and isinstance(generated, GeneratedAnswer):
        return RAGResult(
            question=question,
            request_id=request_id,
            mode=mode,
            k=k,
            messages=state.get('messages', ()),
            generated=generated,
            retrieval_latency_ms=retrieval_latency,
            total_latency_ms=_elapsed_ms(started),
            retrieval_metadata={
                **_interaction_metadata(state, mode, flow_step),
                'next_option_ids': state.get('next_option_ids', ()),
            },
            llm_metadata=generated.llm_metadata,
            raw_provider_response=generated.raw_provider_response,
        )
    if not contexts:
        return RAGResult(
            question=question,
            request_id=request_id,
            mode=mode,
            k=k,
            messages=(),
            generated=GeneratedAnswer(INSUFFICIENT_CONTEXT_ANSWER),
            contexts=(),
            retrieval_latency_ms=retrieval_latency,
            total_latency_ms=_elapsed_ms(started),
            retrieval_metadata=_interaction_metadata(state, mode, flow_step),
        )
    if not isinstance(generated, GeneratedAnswer):
        return RAGResult(
            question=question,
            request_id=request_id,
            mode=mode,
            k=k,
            messages=(),
            generated=GeneratedAnswer(''),
            total_latency_ms=_elapsed_ms(started),
            retrieval_metadata=_fallback_interaction_metadata(
                option_id, flow_step, mode
            ),
        )
    validation = validate_citations(generated.citations, contexts)
    return RAGResult(
        question=question,
        request_id=request_id,
        mode=mode,
        k=k,
        messages=build_messages(question, contexts),
        generated=generated,
        contexts=contexts,
        sources=validation.references,
        invalid_citations=validation.invalid_citations,
        citation_section_paths=validation.matched_section_paths,
        retrieval_latency_ms=retrieval_latency,
        total_latency_ms=_elapsed_ms(started),
        retrieval_metadata=_interaction_metadata(state, mode, flow_step),
        llm_metadata=generated.llm_metadata,
        raw_provider_response=generated.raw_provider_response,
    )


def answer_question(
    question: str,
    *,
    mode: SearchMode = DEFAULT_SEARCH_MODE,
    k: int = 5,
    settings: AgentsSettings | None = None,
    engine: Engine | None = None,
    strategy: SearchStrategy | None = None,
) -> RAGResult:
    """Synchronously answer a question for CLI and synchronous callers."""
    selected_settings = settings or AgentsSettings()
    selected_client = create_llm_client(selected_settings)

    if selected_client is None:
        raise RuntimeError('No LLM client is configured.')
    request_id = uuid4()
    return asyncio.run(
        answer_question_async(
            question,
            mode=mode,
            k=k,
            llm_client=selected_client,
            engine=engine,
            strategy=strategy,
            request_id=request_id,
        )
    )


__all__ = ['RetrievalError', 'answer_question', 'answer_question_async']
