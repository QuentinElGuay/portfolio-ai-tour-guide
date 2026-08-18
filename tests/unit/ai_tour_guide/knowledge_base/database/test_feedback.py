"""Tests for RAG-result and user-feedback persistence schema."""

from sqlalchemy.dialects.postgresql import JSONB, UUID

from ai_tour_guide.knowledge_base.database.feedback import _rag_result_values
from ai_tour_guide.knowledge_base.database.tables import (
    metadata,
    rag_feedback,
    rag_results,
)


def test_rag_results_store_one_result_snapshot_per_request() -> None:
    assert rag_results.name == 'rag_results'
    assert rag_results.metadata is metadata
    assert rag_results.c.request_id.primary_key
    assert isinstance(rag_results.c.request_id.type, UUID)
    assert rag_results.c.rag_trace.nullable is False
    assert isinstance(rag_results.c.rag_trace.type, JSONB)
    assert {
        'rag_result_schema_version',
        'question',
        'answer',
        'search_mode',
        'retrieval_k',
        'outcome',
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


def test_rag_feedback_references_a_rag_result() -> None:
    assert rag_feedback.name == 'rag_feedback'
    assert rag_feedback.metadata is metadata
    assert rag_feedback.c.feedback_id.primary_key
    assert isinstance(rag_feedback.c.request_id.type, UUID)
    assert rag_feedback.c.helpful.nullable is False
    assert {
        foreign_key.target_fullname
        for foreign_key in rag_feedback.c.request_id.foreign_keys
    } == {'rag_results.request_id'}


def test_rag_result_and_feedback_constraints() -> None:
    result_constraints = {constraint.name for constraint in rag_results.constraints}
    feedback_constraints = {constraint.name for constraint in rag_feedback.constraints}

    assert result_constraints >= {
        'ck_rag_results_retrieval_k_positive',
        'ck_rag_results_search_mode',
        'ck_rag_results_outcome',
        'ck_rag_results_counts_non_negative',
    }
    assert feedback_constraints >= {
        'ck_rag_feedback_comment_not_empty',
        'ck_rag_feedback_comment_requires_rating',
    }
    assert {index.name for index in rag_results.indexes} >= {
        'ix_rag_results_search_mode',
        'ix_rag_results_outcome',
    }
    assert {index.name for index in rag_feedback.indexes} >= {
        'ix_rag_feedback_request_id'
    }


def test_rag_result_values_promote_queryable_result_fields() -> None:
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

    assert values['question'] == 'Where should I visit?'
    assert values['answer'] == 'Visit the coast.'
    assert values['outcome'] == 'success'
    assert values['search_result_count'] == 3
    assert values['total_tokens'] == 30
    rag_trace = values['rag_trace']
    assert isinstance(rag_trace, dict)
    assert 'raw_provider_response' not in rag_trace
