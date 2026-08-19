"""Persistence helpers for RAG result snapshots and their user feedback."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from .connection import database_engine
from .tables import rag_ratings, rag_results


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_number(value: object) -> float | None:
    return (
        float(value)
        if isinstance(value, int | float) and not isinstance(value, bool)
        else None
    )


def _optional_rounded_integer(value: object) -> int | None:
    number = _optional_number(value)
    return round(number) if number is not None else None


def _optional_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _items(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _success(error: Mapping[str, Any], contexts: list[object]) -> bool:
    return not error and bool(contexts)


def _rag_result_values(rag_result: Mapping[str, Any]) -> dict[str, object]:
    generated = _mapping(rag_result.get('generated'))
    error = _mapping(rag_result.get('error'))
    contexts = _items(rag_result.get('contexts'))
    llm_metadata = _mapping(rag_result.get('llm_metadata'))
    usage = _mapping(llm_metadata.get('usage'))
    rag_trace = dict(rag_result)
    rag_trace.pop('raw_provider_response', None)

    question = _optional_string(rag_result.get('question'))
    answer = _optional_string(generated.get('answer'))
    search_mode = _optional_string(rag_result.get('mode'))
    retrieval_k = _optional_integer(rag_result.get('k'))
    schema_version = _optional_integer(rag_result.get('schema_version'))
    if (
        question is None
        or answer is None
        or search_mode is None
        or retrieval_k is None
        or schema_version is None
    ):
        raise ValueError('rag_result is missing required fields')

    return {
        'rag_result_schema_version': schema_version,
        'question': question,
        'answer': answer,
        'search_mode': search_mode,
        'retrieval_k': retrieval_k,
        'success': _success(error, contexts),
        'error_stage': _optional_string(error.get('stage')),
        'error_type': _optional_string(error.get('type')),
        'error_message': _optional_string(error.get('message')),
        'retrieval_latency_ms': _optional_rounded_integer(
            rag_result.get('retrieval_latency_ms')
        ),
        'generation_latency_ms': _optional_rounded_integer(
            rag_result.get('generation_latency_ms')
        ),
        'total_latency_ms': _optional_rounded_integer(
            rag_result.get('total_latency_ms')
        ),
        'retrieved_context_count': len(contexts),
        'search_result_count': len(_items(rag_result.get('search_results'))),
        'source_count': len(_items(rag_result.get('sources'))),
        'citation_count': len(_items(generated.get('citations'))),
        'invalid_citation_count': len(_items(rag_result.get('invalid_citations'))),
        'llm_provider': _optional_string(llm_metadata.get('provider')),
        'llm_model': _optional_string(llm_metadata.get('model')),
        'input_tokens': _optional_integer(usage.get('input_tokens')),
        'output_tokens': _optional_integer(usage.get('output_tokens')),
        'total_tokens': _optional_integer(usage.get('total_tokens')),
        'rag_trace': rag_trace,
    }


def store_rag_result(
    request_id: UUID,
    rag_result: Mapping[str, Any],
    *,
    engine: Engine | None = None,
) -> None:
    """Store one immutable RAG result snapshot."""
    with database_engine(engine) as db_engine, db_engine.begin() as connection:
        connection.execute(
            insert(rag_results).values(
                request_id=request_id,
                **_rag_result_values(rag_result),
            )
        )


def store_feedback(
    request_id: UUID,
    helpful: bool,
    comment: str | None = None,
    *,
    engine: Engine | None = None,
) -> bool:
    """Store one user-feedback event for an existing RAG result."""
    with database_engine(engine) as db_engine, db_engine.begin() as connection:
        result_exists = connection.scalar(
            select(rag_results.c.request_id)
            .where(rag_results.c.request_id == request_id)
            .limit(1)
        )
        if result_exists is None:
            return False
        connection.execute(
            insert(rag_ratings).values(
                request_id=request_id,
                helpful=helpful,
                comment=comment,
            )
        )
    return True


__all__ = ['store_feedback', 'store_rag_result']
