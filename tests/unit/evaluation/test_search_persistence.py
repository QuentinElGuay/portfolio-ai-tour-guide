"""Tests for search-evaluation persistence tables."""

from sqlalchemy.dialects.postgresql import JSONB, UUID

from ai_tour_guide.knowledge_base.database.tables.evaluation import (
    metadata,
    search_evaluation_results,
    search_evaluation_runs,
)


def test_search_evaluation_tables_use_dedicated_metadata() -> None:
    assert metadata.tables.keys() == {
        'rag_evaluation_runs',
        'rag_evaluation_results',
        'rag_judge_runs',
        'rag_judge_results',
        'search_evaluation_runs',
        'search_evaluation_results',
    }
    assert search_evaluation_runs.c.run_id.primary_key
    assert isinstance(search_evaluation_runs.c.run_id.type, UUID)
    assert isinstance(search_evaluation_runs.c.configuration.type, JSONB)
    assert search_evaluation_results.c.results.nullable is False
    assert {
        foreign_key.target_fullname
        for foreign_key in search_evaluation_results.c.run_id.foreign_keys
    } == {'search_evaluation_runs.run_id'}


def test_search_evaluation_results_are_unique_per_mode_and_case() -> None:
    primary_key = search_evaluation_results.primary_key
    assert [column.name for column in primary_key.columns] == [
        'run_id',
        'mode',
        'case_id',
    ]
