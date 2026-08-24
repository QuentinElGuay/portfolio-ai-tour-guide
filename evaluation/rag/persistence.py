"""Persistence of per-run RAG evaluation results."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import insert
from sqlalchemy.engine import Engine

from ai_tour_guide.agent.rag.models import RAGResult
from ai_tour_guide.agent.rag.persistence import _usage_event_values
from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.tables.evaluation import (
    rag_evaluation_results,
    rag_evaluation_runs,
    rag_judge_results,
    rag_judge_runs,
)
from ai_tour_guide.knowledge_base.database.tables.public import llm_usage_events
from evaluation.dataset import GoldenCase
from evaluation.rag.judge import JudgeVerdict
from evaluation.rag.metrics import RAGCaseMetrics


def store_rag_evaluation(
    *,
    dataset_path: Path,
    corpus_path: Path,
    mode: str,
    k: int,
    cases: Sequence[GoldenCase],
    results: Sequence[RAGResult],
    metrics: Sequence[RAGCaseMetrics],
    configuration: Mapping[str, object],
    engine: Engine | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    run_id: UUID | None = None,
) -> UUID:
    """Store one completed RAG evaluation and its per-case metrics."""
    if k <= 0:
        raise ValueError('k must be greater than zero')
    if not len(cases) == len(results) == len(metrics):
        raise ValueError('cases, results, and metrics must have the same length')

    run_id = run_id or uuid4()
    finished_at = completed_at or datetime.now(UTC)
    with (
        database_engine(engine, schema_name='evaluation') as db_engine,
        db_engine.begin() as connection,
    ):
        connection.execute(
            insert(rag_evaluation_runs).values(
                run_id=run_id,
                dataset_path=str(dataset_path),
                corpus_path=str(corpus_path),
                mode=mode,
                k=k,
                status='completed',
                configuration=dict(configuration),
                started_at=started_at or finished_at,
                completed_at=finished_at,
            )
        )
        connection.execute(
            insert(rag_evaluation_results),
            [
                _result_values(run_id, case, result, case_metrics)
                for case, result, case_metrics in zip(cases, results, metrics)
            ],
        )
    return run_id


def store_rag_judgements(
    *,
    rag_run_id: UUID,
    provider: str,
    model: str,
    cases: Sequence[GoldenCase],
    results: Sequence[RAGResult],
    judgements: Sequence[JudgeVerdict],
    configuration: Mapping[str, object],
    engine: Engine | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    run_id: UUID | None = None,
) -> UUID:
    """Store judge verdicts for one previously persisted RAG evaluation run."""
    if not len(cases) == len(results) == len(judgements):
        raise ValueError('cases, results, and judgements must have the same length')

    run_id = run_id or uuid4()
    finished_at = completed_at or datetime.now(UTC)
    with (
        database_engine(engine, schema_name='evaluation') as db_engine,
        db_engine.begin() as connection,
    ):
        connection.execute(
            insert(rag_judge_runs).values(
                run_id=run_id,
                rag_run_id=rag_run_id,
                provider=provider,
                model=model,
                status='completed',
                configuration=dict(configuration),
                started_at=started_at or finished_at,
                completed_at=finished_at,
            )
        )
        connection.execute(
            insert(rag_judge_results),
            [
                _judge_values(run_id, case, result, verdict)
                for case, result, verdict in zip(cases, results, judgements)
            ],
        )
        usage_events = [
            event
            for result, verdict in zip(results, judgements)
            if (
                event := _usage_event_values(
                    request_id=result.request_id,
                    rag_run_id=rag_run_id,
                    judge_run_id=run_id,
                    call_type='judge',
                    provider=provider,
                    model=model,
                    usage=(
                        verdict_usage
                        if isinstance(
                            verdict_usage := verdict.metadata.get('usage'), Mapping
                        )
                        else {}
                    ),
                    connection=connection,
                )
            )
            is not None
        ]
        if usage_events:
            connection.execute(insert(llm_usage_events), usage_events)
    return run_id


def _judge_values(
    run_id: UUID,
    case: GoldenCase,
    result: RAGResult,
    verdict: JudgeVerdict,
) -> dict[str, object]:
    return {
        'run_id': run_id,
        'request_id': result.request_id,
        'case_id': case.case_id,
        'answer_correct': verdict.correct,
        'judge_latency_ms': verdict.latency_ms,
        'judge_reason': verdict.reason,
        'judge_metadata': dict(verdict.metadata),
    }


def _result_values(
    run_id: UUID,
    case: GoldenCase,
    result: RAGResult,
    metrics: RAGCaseMetrics,
) -> dict[str, object]:
    source = case.expected.relevant_source
    return {
        'run_id': run_id,
        'request_id': result.request_id,
        'case_id': case.case_id,
        'category': case.category,
        'answerable': case.expected.answerable,
        'reference_answer': case.expected.reference_answer,
        'expected_source_url': source.source_url if source else None,
        'expected_source_version': source.version if source else None,
        'expected_section_path': list(source.section_path) if source else None,
        'source_precision': metrics.source_precision,
        'source_recall': metrics.source_recall,
        'section_precision': metrics.section_precision,
        'section_recall': metrics.section_recall,
        'citation_validity': metrics.citation_validity,
        'citation_coverage': metrics.citation_coverage,
        'refused': metrics.refused,
        'refusal_correct': metrics.refusal_correct,
        'error': metrics.error,
        'retrieval_latency_ms': metrics.retrieval_latency_ms,
        'generation_latency_ms': metrics.generation_latency_ms,
        'total_latency_ms': metrics.total_latency_ms,
    }


__all__ = ['store_rag_evaluation', 'store_rag_judgements']
