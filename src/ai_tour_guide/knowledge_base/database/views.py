"""Curated reporting views for operational and offline dashboards."""

from sqlalchemy import Connection, text

EVALUATION_VIEW_NAMES = (
    'search_evaluation_summary',
    'rag_evaluation_summary',
    'judge_evaluation_summary',
    'llm_evaluation_cost_summary',
)
OPERATIONAL_VIEW_NAMES = ('llm_operational_cost_summary',)


def create_operational_views(connection: Connection, *, schema_name: str) -> None:
    """Create reporting views for billable production LLM usage."""
    if schema_name != 'public':
        raise ValueError('operational views can only be created in the public schema')
    for statement in _operational_view_statements(schema_name):
        connection.execute(text(statement))


def create_evaluation_views(connection: Connection, *, schema_name: str) -> None:
    """Create or replace the evaluation reporting views in ``schema_name``."""
    if schema_name != 'evaluation':
        raise ValueError(
            'evaluation views can only be created in the evaluation schema'
        )

    for view_name in ('rag_evaluation_cost_summary', 'judge_evaluation_cost_summary'):
        connection.execute(text(f'DROP VIEW IF EXISTS {schema_name}.{view_name}'))
    for statement in _evaluation_view_statements(schema_name):
        connection.execute(text(statement))


def _evaluation_view_statements(schema_name: str) -> tuple[str, ...]:
    return (
        f"""
        CREATE OR REPLACE VIEW {schema_name}.search_evaluation_summary AS
        SELECT
            run.run_id,
            run.completed_at AS evaluation_time,
            result.mode,
            run.k,
            COUNT(*) AS evaluated_cases,
            AVG(result.raw_hit_rate_at_k) AS hit_rate_at_k,
            AVG(result.raw_recall_at_k) AS recall_at_k,
            AVG(result.raw_reciprocal_rank) AS mean_reciprocal_rank,
            AVG(result.search_latency_ms) AS mean_search_latency_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY result.search_latency_ms
            ) AS p95_search_latency_ms
        FROM {schema_name}.search_evaluation_runs AS run
        JOIN {schema_name}.search_evaluation_results AS result
          ON result.run_id = run.run_id
        WHERE run.status = 'completed'
        GROUP BY run.run_id, run.completed_at, result.mode, run.k
        """,
        f"""
        CREATE OR REPLACE VIEW {schema_name}.rag_evaluation_summary AS
        SELECT
            run.run_id,
            run.completed_at AS evaluation_time,
            run.mode,
            run.k,
            COUNT(*) AS evaluated_cases,
            AVG(result.source_precision) AS source_precision,
            AVG(result.source_recall) AS source_recall,
            AVG(result.section_precision) AS section_precision,
            AVG(result.section_recall) AS section_recall,
            AVG(result.citation_validity) AS citation_validity,
            AVG(result.citation_coverage) AS citation_coverage,
            AVG(CASE WHEN result.refused THEN 1.0 ELSE 0.0 END)
                AS refusal_rate,
            AVG(CASE WHEN result.refusal_correct THEN 1.0 ELSE 0.0 END)
                AS refusal_accuracy,
            AVG(CASE WHEN result.error THEN 1.0 ELSE 0.0 END)
                AS error_rate,
            AVG(result.retrieval_latency_ms) AS mean_retrieval_latency_ms,
            AVG(result.generation_latency_ms) AS mean_generation_latency_ms,
            AVG(result.total_latency_ms) AS mean_total_latency_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY result.retrieval_latency_ms
            ) AS p95_retrieval_latency_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY result.generation_latency_ms
            ) AS p95_generation_latency_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY result.total_latency_ms
            ) AS p95_total_latency_ms
        FROM {schema_name}.rag_evaluation_runs AS run
        JOIN {schema_name}.rag_evaluation_results AS result
          ON result.run_id = run.run_id
        WHERE run.status = 'completed'
        GROUP BY run.run_id, run.completed_at, run.mode, run.k
        """,
        f"""
        CREATE OR REPLACE VIEW {schema_name}.judge_evaluation_summary AS
        SELECT
            judge.run_id AS judge_run_id,
            judge.rag_run_id,
            judge.completed_at AS evaluation_time,
            rag.mode,
            rag.k,
            judge.provider,
            judge.model,
            COUNT(*) AS evaluated_cases,
            AVG(CASE WHEN result.answer_correct THEN 1.0 ELSE 0.0 END)
                AS answer_correct_rate,
            AVG(result.judge_latency_ms) AS mean_judge_latency_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY result.judge_latency_ms
            ) AS p95_judge_latency_ms
        FROM {schema_name}.rag_judge_runs AS judge
        JOIN {schema_name}.rag_evaluation_runs AS rag
          ON rag.run_id = judge.rag_run_id
        JOIN {schema_name}.rag_judge_results AS result
          ON result.run_id = judge.run_id
        WHERE judge.status = 'completed'
        GROUP BY
            judge.run_id,
            judge.rag_run_id,
            judge.completed_at,
            rag.mode,
            rag.k,
            judge.provider,
            judge.model
        """,
        f"""
        CREATE OR REPLACE VIEW {schema_name}.llm_evaluation_cost_summary AS
        WITH evaluation_runs AS (
            SELECT
                'rag'::text AS evaluation_type,
                run.run_id,
                run.run_id AS rag_run_id,
                NULL::uuid AS judge_run_id,
                run.completed_at AS evaluation_time,
                NULL::text AS provider,
                NULL::text AS model
            FROM {schema_name}.rag_evaluation_runs AS run
            WHERE run.status = 'completed'

            UNION ALL

            SELECT
                'judge'::text AS evaluation_type,
                judge.run_id,
                judge.rag_run_id,
                judge.run_id AS judge_run_id,
                judge.completed_at AS evaluation_time,
                judge.provider,
                judge.model
            FROM {schema_name}.rag_judge_runs AS judge
            WHERE judge.status = 'completed'
        ), usage AS (
            SELECT
                evaluation_type,
                rag_run_id,
                judge_run_id,
                COUNT(*) AS llm_calls,
                MAX(provider) AS provider,
                MAX(model) AS model,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(total_cost), 0) AS total_cost,
                MAX(currency) AS currency
            FROM (
                SELECT
                    'rag'::text AS evaluation_type,
                    rag_run_id,
                    NULL::uuid AS judge_run_id,
                    provider,
                    model,
                    input_tokens,
                    cached_input_tokens,
                    output_tokens,
                    total_tokens,
                    total_cost,
                    currency
                FROM {schema_name}.llm_usage_events
                WHERE call_type = 'answer' AND rag_run_id IS NOT NULL

                UNION ALL

                SELECT
                    'judge'::text AS evaluation_type,
                    rag_run_id,
                    judge_run_id,
                    provider,
                    model,
                    input_tokens,
                    cached_input_tokens,
                    output_tokens,
                    total_tokens,
                    total_cost,
                    currency
                FROM {schema_name}.llm_usage_events
                WHERE call_type = 'judge' AND judge_run_id IS NOT NULL
            ) AS events
            GROUP BY evaluation_type, rag_run_id, judge_run_id
        )
        SELECT
            runs.evaluation_type,
            runs.run_id,
            runs.rag_run_id,
            runs.judge_run_id,
            runs.evaluation_time,
            COALESCE(usage.provider, runs.provider) AS provider,
            COALESCE(usage.model, runs.model) AS model,
            COALESCE(usage.llm_calls, 0) AS llm_calls,
            COALESCE(usage.input_tokens, 0) AS input_tokens,
            COALESCE(usage.cached_input_tokens, 0) AS cached_input_tokens,
            COALESCE(usage.output_tokens, 0) AS output_tokens,
            COALESCE(usage.total_tokens, 0) AS total_tokens,
            COALESCE(usage.total_cost, 0) AS total_cost,
            COALESCE(usage.currency, 'USD') AS currency
        FROM evaluation_runs AS runs
        LEFT JOIN usage
          ON usage.evaluation_type = runs.evaluation_type
         AND usage.rag_run_id IS NOT DISTINCT FROM runs.rag_run_id
         AND usage.judge_run_id IS NOT DISTINCT FROM runs.judge_run_id
        """,
    )


def _operational_view_statements(schema_name: str) -> tuple[str, ...]:
    return (
        f"""
        CREATE OR REPLACE VIEW {schema_name}.llm_operational_cost_summary AS
        SELECT
            DATE_TRUNC('day', created_at) AS usage_date,
            call_type,
            provider,
            model,
            COUNT(*) AS llm_calls,
            COALESCE(SUM(input_tokens), 0) AS input_tokens,
            COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
            COALESCE(SUM(output_tokens), 0) AS output_tokens,
            COALESCE(SUM(total_tokens), 0) AS total_tokens,
            COALESCE(SUM(total_cost), 0) AS total_cost,
            COALESCE(currency, 'USD') AS currency
        FROM {schema_name}.llm_usage_events
        GROUP BY
            DATE_TRUNC('day', created_at),
            call_type,
            provider,
            model,
            COALESCE(currency, 'USD')
        """,
    )


__all__ = [
    'EVALUATION_VIEW_NAMES',
    'OPERATIONAL_VIEW_NAMES',
    'create_evaluation_views',
    'create_operational_views',
]
