"""Persistence of completed search-evaluation results."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import insert
from sqlalchemy.engine import Engine

from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.tables.evaluation import (
    search_evaluation_results,
    search_evaluation_runs,
)

_REQUIRED_RESULT_FIELDS = (
    'id',
    'category',
    'search_latency_ms',
    'raw_hit_rate_at_k',
    'raw_recall_at_k',
    'raw_reciprocal_rank',
    'results',
)


def store_search_evaluation(
    *,
    dataset_path: Path,
    corpus_path: Path,
    k: int,
    configuration: Mapping[str, object],
    results: Mapping[str, Sequence[Mapping[str, object]]],
    engine: Engine | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> UUID:
    """Store one completed search evaluation and all of its ranked results."""
    if k <= 0:
        raise ValueError('k must be greater than zero')
    run_id = uuid4()
    finished_at = completed_at or datetime.now(UTC)
    with (
        database_engine(engine, schema_name='evaluation') as db_engine,
        db_engine.begin() as connection,
    ):
        connection.execute(
            insert(search_evaluation_runs).values(
                run_id=run_id,
                dataset_path=str(dataset_path),
                corpus_path=str(corpus_path),
                k=k,
                status='completed',
                configuration=dict(configuration),
                started_at=started_at or finished_at,
                completed_at=finished_at,
            )
        )
        for mode, mode_results in results.items():
            for metrics in mode_results:
                _validate_result(metrics)
                connection.execute(
                    insert(search_evaluation_results).values(
                        run_id=run_id,
                        mode=mode,
                        case_id=metrics['id'],
                        category=metrics['category'],
                        search_latency_ms=metrics['search_latency_ms'],
                        raw_hit_rate_at_k=metrics['raw_hit_rate_at_k'],
                        raw_recall_at_k=metrics['raw_recall_at_k'],
                        raw_reciprocal_rank=metrics['raw_reciprocal_rank'],
                        results=metrics['results'],
                    )
                )
    return run_id


def _validate_result(metrics: Mapping[str, object]) -> None:
    if any(field not in metrics for field in _REQUIRED_RESULT_FIELDS):
        raise ValueError('metrics is missing required search-evaluation fields')


__all__ = ['store_search_evaluation']
