"""Application orchestration for retrieval-augmented answers."""

import asyncio
import logging
from time import perf_counter

from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.llm.factory import create_default_llm_client
from ai_tour_guide.agent.llm.interfaces import GenerationError, LLMClient
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGError, RAGResult
from ai_tour_guide.agent.rag.prompting import build_messages
from ai_tour_guide.agent.rag.sources import validate_citations
from ai_tour_guide.agent.responses import (
    GENERATION_ERROR_ANSWER,
    INSUFFICIENT_CONTEXT_ANSWER,
    LLM_CONFIGURATION_REQUIRED_ANSWER,
    RETRIEVAL_ERROR_ANSWER,
)
from ai_tour_guide.knowledge_base.retrieval.context import retrieve_context
from ai_tour_guide.knowledge_base.search import SearchMode

logger = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """An expected knowledge-base operational failure."""


def _error(stage: str, exc: Exception) -> RAGError:
    logger.exception('%s failed', stage)
    return RAGError(stage=stage, type=type(exc).__name__, message=str(exc))


def answer_question(
    question: str,
    *,
    mode: SearchMode = SearchMode.VECTOR,
    k: int = 5,
    client: LLMClient | None = None,
) -> RAGResult:
    """Retrieve evidence, generate a cited answer, and retain its full trace."""
    started = perf_counter()
    selected_mode = SearchMode(mode)

    selected_client = client or create_default_llm_client()
    if selected_client is None:
        raise RuntimeError('No LLM client is configured.')

    retrieval_started = perf_counter()

    try:
        contexts = retrieve_context(
                question,
                search_mode=selected_mode,
                k=k,
            )
    except (OSError, SQLAlchemyError) as exc:
        retrieval_latency = (perf_counter() - retrieval_started) * 1000

        return RAGResult(
            question=question,
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
        generated = asyncio.run(
            selected_client.answer_question(messages)
        )
    except GenerationError as exc:
        generation_latency = (perf_counter() - generation_started) * 1000

        return RAGResult(
            question=question,
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
        mode=selected_mode,
        k=k,
        messages=messages,
        generated=generated,
        contexts=contexts,
        sources=sources,
        invalid_citations=validation.invalid_citations,
        retrieval_latency_ms=retrieval_latency,
        generation_latency_ms=generation_latency,
        total_latency_ms=(perf_counter() - started) * 1000,
        retrieval_metadata={
            'mode': selected_mode.value,
        },
        llm_metadata=generated.llm_metadata,
        raw_provider_response=generated.raw_provider_response,
    )


__all__ = ['RetrievalError', 'answer_question']
