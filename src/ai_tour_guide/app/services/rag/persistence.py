"""Persistence helpers for RAG result snapshots and their user feedback."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.tables.public import (
    llm_model_pricing,
    llm_usage_events,
    rag_results,
)


class UnimplementedModelError(ValueError):
    """Raised when a billable LLM model has no configured pricing."""


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


def _usage_event_values(
    *,
    request_id: UUID,
    rag_run_id: UUID | None,
    judge_run_id: UUID | None,
    call_type: str,
    provider: object,
    model: object,
    usage: Mapping[str, Any],
    connection,
) -> dict[str, object] | None:
    provider_name = _optional_string(provider)
    model_name = _optional_string(model)
    input_tokens = _optional_integer(usage.get('input_tokens'))
    output_tokens = _optional_integer(usage.get('output_tokens'))
    total_tokens = _optional_integer(usage.get('total_tokens'))
    input_details = _mapping(usage.get('input_tokens_details'))
    cached_input_tokens = _optional_integer(input_details.get('cached_tokens'))
    if (
        provider_name is None
        or model_name is None
        or (input_tokens is None and output_tokens is None and total_tokens is None)
    ):
        return None

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    pricing = (
        connection.execute(
            select(llm_model_pricing)
            .where(
                llm_model_pricing.c.provider == provider_name,
                llm_model_pricing.c.model == model_name,
            )
            .order_by(llm_model_pricing.c.effective_from.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if pricing is None:
        raise UnimplementedModelError(
            f'No pricing configured for LLM model {provider_name}/{model_name}; '
            'add it to llm_model_pricing before using this model.'
        )
    input_cost = output_cost = total_cost = None
    currency = None
    pricing_id = None
    pricing_id = pricing['pricing_id']
    currency = pricing['currency']
    cached = min(cached_input_tokens or 0, input_tokens or 0)
    regular_input = max((input_tokens or 0) - cached, 0)
    input_cost = (
        Decimal(regular_input) * pricing['input_cost_per_token']
        + Decimal(cached) * pricing['cached_input_cost_per_token']
    )
    output_cost = Decimal(output_tokens or 0) * pricing['output_cost_per_token']
    total_cost = input_cost + output_cost
    return {
        'request_id': request_id,
        'rag_run_id': rag_run_id,
        'judge_run_id': judge_run_id,
        'call_type': call_type,
        'provider': provider_name,
        'model': model_name,
        'input_tokens': input_tokens,
        'cached_input_tokens': cached_input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': total_tokens,
        'pricing_id': pricing_id,
        'input_cost': input_cost,
        'output_cost': output_cost,
        'total_cost': total_cost,
        'currency': currency,
        'metadata': dict(usage),
    }


def _items(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _success(error: Mapping[str, Any], contexts: list[object]) -> bool:
    # Until separating Answer and RAGResult, ignore missing context
    return not error  # and bool(contexts)


def _rag_result_values(rag_result: Mapping[str, Any]) -> dict[str, object]:
    generated = _mapping(rag_result.get('generated'))
    error = _mapping(rag_result.get('error'))
    contexts = _items(rag_result.get('contexts'))
    llm_metadata = _mapping(rag_result.get('llm_metadata'))
    usage = _mapping(llm_metadata.get('usage'))
    rag_trace = dict(rag_result)
    rag_trace.pop('question', None)
    rag_trace.pop('messages', None)
    rag_trace.pop('generated', None)
    rag_trace.pop('raw_provider_response', None)

    search_mode = _optional_string(rag_result.get('mode'))
    retrieval_k = _optional_integer(rag_result.get('k'))
    schema_version = _optional_integer(rag_result.get('schema_version'))
    if search_mode is None or retrieval_k is None or schema_version is None:
        raise ValueError('rag_result is missing required fields')

    return {
        'rag_result_schema_version': schema_version,
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
    evaluation_run_id: UUID | None = None,
) -> None:
    """Store one immutable RAG result snapshot."""
    with database_engine(engine) as db_engine, db_engine.begin() as connection:
        values = _rag_result_values(rag_result)
        connection.execute(
            insert(rag_results).values(
                request_id=request_id,
                **values,
            )
        )
        usage = _mapping(_mapping(rag_result.get('llm_metadata')).get('usage'))
        usage_event = _usage_event_values(
            request_id=request_id,
            rag_run_id=evaluation_run_id,
            judge_run_id=None,
            call_type='answer',
            provider=values['llm_provider'],
            model=values['llm_model'],
            usage=usage,
            connection=connection,
        )
        if usage_event is not None:
            connection.execute(insert(llm_usage_events).values(usage_event))


__all__ = ['UnimplementedModelError', 'store_rag_result']
