"""Tests for evaluation reporting views."""

from typing import cast

import pytest
from sqlalchemy import Connection

from ai_tour_guide.knowledge_base.database.views import (
    EVALUATION_VIEW_NAMES,
    OPERATIONAL_VIEW_NAMES,
    _evaluation_view_statements,
    _operational_view_statements,
)


def test_evaluation_view_names_are_stable() -> None:
    statements = _evaluation_view_statements('evaluation')

    assert len(statements) == len(EVALUATION_VIEW_NAMES)
    for view_name, statement in zip(EVALUATION_VIEW_NAMES, statements):
        assert f'VIEW evaluation.{view_name} AS' in statement


@pytest.mark.parametrize(
    'view_name, expected_columns',
    [
        (
            'search_evaluation_summary',
            ('hit_rate_at_k', 'recall_at_k', 'mean_reciprocal_rank'),
        ),
        (
            'rag_evaluation_summary',
            ('source_precision', 'citation_validity', 'refusal_accuracy'),
        ),
        (
            'judge_evaluation_summary',
            ('answer_correct_rate', 'mean_judge_latency_ms'),
        ),
        (
            'llm_evaluation_cost_summary',
            ('evaluation_type', 'provider', 'model', 'total_cost', 'total_tokens'),
        ),
    ],
)
def test_evaluation_views_expose_dashboard_metrics(
    view_name: str, expected_columns: tuple[str, ...]
) -> None:
    statement = next(
        statement
        for name, statement in zip(
            EVALUATION_VIEW_NAMES, _evaluation_view_statements('evaluation')
        )
        if name == view_name
    )

    for column in expected_columns:
        assert f'AS {column}' in statement


def test_evaluation_views_reject_other_schemas() -> None:
    from sqlalchemy import create_mock_engine

    from ai_tour_guide.knowledge_base.database.views import create_evaluation_views

    with pytest.raises(ValueError, match='evaluation schema'):
        create_evaluation_views(
            cast(
                Connection,
                create_mock_engine('postgresql+psycopg://', lambda *_args: None),
            ),
            schema_name='public',
        )


def test_fixture_evaluation_without_usage_has_zero_cost() -> None:
    """Keep fixture-backed evaluations visible as zero-cost runs."""
    statement = next(
        statement
        for name, statement in zip(
            EVALUATION_VIEW_NAMES, _evaluation_view_statements('evaluation')
        )
        if name == 'llm_evaluation_cost_summary'
    )

    assert "'rag'::text AS evaluation_type" in statement
    assert 'LEFT JOIN usage' in statement
    assert 'COALESCE(usage.total_cost, 0) AS total_cost' in statement
    assert 'COALESCE(usage.llm_calls, 0) AS llm_calls' in statement


def test_operational_cost_view_uses_usd_for_missing_currency() -> None:
    """Keep the operational Metabase chart on a concrete currency."""
    statements = _operational_view_statements('public')

    assert len(statements) == len(OPERATIONAL_VIEW_NAMES)
    statement = statements[0]
    assert 'VIEW public.llm_operational_cost_summary AS' in statement
    assert "COALESCE(currency, 'USD') AS currency" in statement
