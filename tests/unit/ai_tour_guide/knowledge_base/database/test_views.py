"""Tests for evaluation reporting views."""

import pytest

from ai_tour_guide.knowledge_base.database.views import (
    EVALUATION_VIEW_NAMES,
    _evaluation_view_statements,
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
    ],
)
def test_evaluation_views_expose_dashboard_metrics(
    view_name: str, expected_columns: tuple[str, ...]
) -> None:
    statement = dict(
        zip(EVALUATION_VIEW_NAMES, _evaluation_view_statements('evaluation'))
    )[view_name]

    for column in expected_columns:
        assert f'AS {column}' in statement


def test_evaluation_views_reject_other_schemas() -> None:
    from sqlalchemy import create_mock_engine

    from ai_tour_guide.knowledge_base.database.views import create_evaluation_views

    with pytest.raises(ValueError, match='evaluation schema'):
        create_evaluation_views(
            create_mock_engine('postgresql+psycopg://', lambda *_args: None),
            schema_name='public',
        )
