"""Application orchestration for retrieval-augmented answers."""

from __future__ import annotations

import asyncio
import logging
from time import perf_counter

from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.llm.factory import create_default_llm_client
from ai_tour_guide.agent.llm.interfaces import GenerationError, LLMClient
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGError, RAGResult
from ai_tour_guide.agent.rag.prompting import build_context, build_messages
from ai_tour_guide.agent.rag.sources import validate_citations
from ai_tour_guide.agent.responses import (
    GENERATION_ERROR_ANSWER,
    INSUFFICIENT_CONTEXT_ANSWER,
    RETRIEVAL_ERROR_ANSWER,
)
from ai_tour_guide.knowledge_base.retrieval import SearchMode, retrieve

logger = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """An expected knowledge-base operational failure."""


def _error(stage: str, exc: Exception) -> RAGError:
    logger.exception('%s failed', stage)
    return RAGError(stage=stage, type=type(exc).__name__, message=str(exc))


def answer_question(
    question: str,
    *,
    mode: SearchMode = 'vector',
    k: int = 5,
    client: LLMClient | None = None,
) -> RAGResult:
    """Retrieve evidence, generate a cited answer, and retain its full trace."""
    started = perf_counter()
    selected_client = client or create_default_llm_client()
    if selected_client is None:
        raise RuntimeError('No LLM client is configured.')
    try:
        retrieval_started = perf_counter()
        retrieved = tuple(retrieve(question, mode=mode, k=k))
        retrieval_latency = (perf_counter() - retrieval_started) * 1000
    except (OSError, SQLAlchemyError) as exc:
        return RAGResult(
            question=question,
            mode=SearchMode(mode),
            k=k,
            context='',
            messages=(),
            generated=GeneratedAnswer(RETRIEVAL_ERROR_ANSWER),
            error=_error('retrieval', exc),
            retrieval_latency_ms=(perf_counter() - started) * 1000,
            total_latency_ms=(perf_counter() - started) * 1000,
        )
    if not retrieved:
        return RAGResult(
            question=question,
            mode=SearchMode(mode),
            k=k,
            context='',
            messages=(),
            generated=GeneratedAnswer(INSUFFICIENT_CONTEXT_ANSWER),
            retrieved=(),
            retrieval_latency_ms=retrieval_latency,
            total_latency_ms=(perf_counter() - started) * 1000,
        )
    context = build_context(retrieved)
    messages = tuple(build_messages(question, context))
    try:
        generation_started = perf_counter()
        generated = asyncio.run(selected_client.answer_question(messages))
        generation_latency = (perf_counter() - generation_started) * 1000
    except GenerationError as exc:
        return RAGResult(
            question=question,
            mode=SearchMode(mode),
            k=k,
            context=context,
            messages=messages,
            generated=GeneratedAnswer(GENERATION_ERROR_ANSWER),
            retrieved=retrieved,
            error=_error('generation', exc),
            retrieval_latency_ms=retrieval_latency,
            generation_latency_ms=(perf_counter() - generation_started) * 1000,
            total_latency_ms=(perf_counter() - started) * 1000,
        )
    validation = validate_citations(generated.citations, retrieved)
    sources = (
        ()
        if generated.answer.strip() == INSUFFICIENT_CONTEXT_ANSWER
        else validation.references
    )
    return RAGResult(
        question=question,
        mode=SearchMode(mode),
        k=k,
        context=context,
        messages=messages,
        generated=generated,
        retrieved=retrieved,
        sources=sources,
        invalid_citations=validation.invalid_citations,
        retrieval_latency_ms=retrieval_latency,
        generation_latency_ms=generation_latency,
        total_latency_ms=(perf_counter() - started) * 1000,
        retrieval_metadata={'mode': SearchMode(mode).value},
        llm_metadata=generated.llm_metadata,
        raw_provider_response=generated.raw_provider_response,
    )


__all__ = ['RetrievalError', 'answer_question']
