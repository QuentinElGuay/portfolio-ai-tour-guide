"""Application orchestration for retrieval-augmented answers."""

import asyncio
import logging
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.llm.clients import (
    GenerationError,
    LLMClient,
)
from ai_tour_guide.agent.llm.factory import create_llm_client
from ai_tour_guide.agent.llm.settings import AgentsSettings
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGError, RAGResult
from ai_tour_guide.agent.rag.prompting import build_messages
from ai_tour_guide.agent.rag.sources import validate_citations
from ai_tour_guide.agent.responses import (
    GENERATION_ERROR_ANSWER,
    INSUFFICIENT_CONTEXT_ANSWER,
    RETRIEVAL_ERROR_ANSWER,
)
from ai_tour_guide.knowledge_base.retrieval.context import retrieve_context
from ai_tour_guide.knowledge_base.search import DEFAULT_SEARCH_MODE, SearchMode
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy

logger = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """An expected knowledge-base operational failure."""


def _error(stage: str, exc: Exception) -> RAGError:
    logger.exception('%s failed', stage)
    return RAGError(stage=stage, type=type(exc).__name__, message=str(exc))


async def answer_question_async(
    question: str,
    *,
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

    retrieval_started = perf_counter()

    try:
        contexts = retrieve_context(
            question,
            search_mode=selected_mode,
            k=k,
            engine=engine,
            strategy=strategy,
        )
    except (OSError, SQLAlchemyError) as exc:
        retrieval_latency = (perf_counter() - retrieval_started) * 1000

        return RAGResult(
            question=question,
            request_id=selected_request_id,
            mode=selected_mode,
            k=k,
            messages=(),
            generated=GeneratedAnswer(RETRIEVAL_ERROR_ANSWER),
            error=_error('retrieval', exc),
            retrieval_latency_ms=retrieval_latency,
            total_latency_ms=(perf_counter() - started) * 1000,
        )

    retrieval_latency = (perf_counter() - retrieval_started) * 1000

    if not contexts:
        return RAGResult(
            question=question,
            request_id=selected_request_id,
            mode=selected_mode,
            k=k,
            messages=(),
            generated=GeneratedAnswer(INSUFFICIENT_CONTEXT_ANSWER),
            contexts=(),
            retrieval_latency_ms=retrieval_latency,
            total_latency_ms=(perf_counter() - started) * 1000,
        )

    messages = build_messages(question, contexts)

    generation_started = perf_counter()

    try:
        generated = await llm_client.answer_question(messages)
    except GenerationError as exc:
        generation_latency = (perf_counter() - generation_started) * 1000

        return RAGResult(
            question=question,
            request_id=selected_request_id,
            mode=selected_mode,
            k=k,
            messages=messages,
            generated=GeneratedAnswer(GENERATION_ERROR_ANSWER),
            contexts=contexts,
            error=_error('generation', exc),
            retrieval_latency_ms=retrieval_latency,
            generation_latency_ms=generation_latency,
            total_latency_ms=(perf_counter() - started) * 1000,
        )

    generation_latency = (perf_counter() - generation_started) * 1000

    validation = validate_citations(
        generated.citations,
        contexts,
    )

    sources = (
        ()
        if generated.answer.strip() == INSUFFICIENT_CONTEXT_ANSWER
        else validation.references
    )

    return RAGResult(
        question=question,
        request_id=selected_request_id,
        mode=selected_mode,
        k=k,
        messages=messages,
        generated=generated,
        contexts=contexts,
        sources=sources,
        invalid_citations=validation.invalid_citations,
        citation_section_paths=validation.matched_section_paths,
        retrieval_latency_ms=retrieval_latency,
        generation_latency_ms=generation_latency,
        total_latency_ms=(perf_counter() - started) * 1000,
        retrieval_metadata={
            'mode': selected_mode.value,
        },
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
