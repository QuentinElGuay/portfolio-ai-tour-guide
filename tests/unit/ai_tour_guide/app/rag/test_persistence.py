"""Tests for RAG-result and user-feedback persistence schema."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ai_tour_guide.app.services.rag.persistence import (
    UnimplementedModelError,
    _rag_result_values,
    _usage_event_values,
)
from ai_tour_guide.knowledge_base.database.tables.public import (
    chat_feedback,
    chat_messages,
    metadata,
    rag_results,
)


def test_rag_results_store_one_result_snapshot_per_request() -> None:
    """Verify that rag results store one result snapshot per request."""
    assert rag_results.name == 'rag_results'
    assert rag_results.metadata is metadata
    assert rag_results.c.request_id.primary_key
    assert isinstance(rag_results.c.request_id.type, UUID)
    assert rag_results.c.rag_trace.nullable is False
    assert isinstance(rag_results.c.rag_trace.type, JSONB)
    assert {
        'rag_result_schema_version',
        'search_mode',
        'retrieval_k',
        'success',
        'retrieval_latency_ms',
        'generation_latency_ms',
        'total_latency_ms',
        'retrieved_context_count',
        'search_result_count',
        'source_count',
        'citation_count',
        'invalid_citation_count',
        'llm_provider',
        'llm_model',
        'input_tokens',
        'output_tokens',
        'total_tokens',
    } <= set(rag_results.c.keys())


def test_chat_feedback_references_a_chat_message() -> None:
    """Verify that feedback is owned by generic chat messages."""
    assert chat_messages.name == 'chat_messages'
    assert chat_messages.metadata is metadata
    assert chat_feedback.name == 'chat_feedback'
    assert chat_feedback.metadata is metadata
    assert chat_feedback.c.feedback_id.primary_key
    assert isinstance(chat_feedback.c.message_id.type, UUID)
    assert chat_feedback.c.helpful.nullable is False
    assert {
        foreign_key.target_fullname
        for foreign_key in chat_feedback.c.message_id.foreign_keys
    } == {'chat_messages.message_id'}


def test_rag_result_and_feedback_constraints() -> None:
    """Verify that rag result and feedback constraints."""
    result_constraints = {constraint.name for constraint in rag_results.constraints}
    feedback_constraints = {constraint.name for constraint in chat_feedback.constraints}

    assert result_constraints >= {
        'ck_rag_results_retrieval_k_positive',
        'ck_rag_results_search_mode',
        'ck_rag_results_counts_non_negative',
    }
    assert feedback_constraints >= {
        'ck_rag_feedback_comment_not_empty',
        'ck_rag_feedback_comment_requires_rating',
    }
    assert {index.name for index in rag_results.indexes} >= {
        'ix_rag_results_search_mode',
        'ix_rag_results_success',
    }
    assert {index.name for index in chat_feedback.indexes} >= {
        'ix_chat_feedback_message_id'
    }


def test_rag_result_values_promote_queryable_result_fields() -> None:
    """Verify that rag result values promote queryable result fields."""
    values = _rag_result_values(
        {
            'schema_version': 1,
            'question': 'Where should I visit?',
            'mode': 'hybrid',
            'k': 5,
            'generated': {
                'answer': 'Visit the coast.',
                'citations': [{}, {}],
            },
            'contexts': [{}, {}],
            'search_results': [{}, {}, {}],
            'sources': [{}],
            'invalid_citations': [{}],
            'retrieval_latency_ms': 12.5,
            'generation_latency_ms': 50.5,
            'total_latency_ms': 63.0,
            'llm_metadata': {
                'provider': 'openai',
                'model': 'gpt-test',
                'usage': {
                    'input_tokens': 10,
                    'output_tokens': 20,
                    'total_tokens': 30,
                },
            },
            'raw_provider_response': {'sensitive': 'diagnostic payload'},
        }
    )

    assert 'question' not in values
    assert 'answer' not in values
    assert values['success'] is True
    assert values['search_result_count'] == 3
    assert values['total_tokens'] == 30
    rag_trace = values['rag_trace']
    assert isinstance(rag_trace, dict)
    assert 'question' not in rag_trace
    assert 'messages' not in rag_trace
    assert 'generated' not in rag_trace
    assert 'raw_provider_response' not in rag_trace


def test_usage_event_rejects_model_without_pricing() -> None:
    """Fail fast instead of recording an unpriced billable LLM call."""
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.first.return_value = None

    with pytest.raises(UnimplementedModelError, match='openai/unknown-model'):
        _usage_event_values(
            request_id=uuid4(),
            rag_run_id=None,
            judge_run_id=None,
            call_type='answer',
            provider='openai',
            model='unknown-model',
            usage={'input_tokens': 10, 'output_tokens': 5},
            connection=connection,
        )
