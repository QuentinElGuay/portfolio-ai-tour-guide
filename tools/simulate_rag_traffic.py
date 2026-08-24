"""Populate operational dashboards with deterministic synthetic RAG traffic."""

import argparse
import asyncio
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, insert, select, update

from ai_tour_guide.agent.llm.fixture import FixtureLLMClient
from ai_tour_guide.agent.rag.persistence import (
    _usage_event_values,
    store_rag_result,
)
from ai_tour_guide.agent.rag.pipeline import answer_question_async
from ai_tour_guide.agent.responses import GENERATION_ERROR_ANSWER
from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, corpus_context
from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.tables.public import (
    llm_usage_events,
    rag_ratings,
    rag_results,
)
from ai_tour_guide.knowledge_base.search import DEFAULT_SEARCH_MODE, SearchMode
from ai_tour_guide.knowledge_base.search.strategies import create_search_strategy
from evaluation.dataset import (
    DEFAULT_DATASET_ROOT,
    GoldenCase,
    golden_dataset_path,
    load_golden_dataset,
)


def _simulated_timestamp(
    *, now: datetime, day_index: int, slot: int, requests_per_day: int, days: int
) -> datetime:
    day = now - timedelta(days=days - day_index - 1)
    minutes = (slot * 1_440 // requests_per_day) % 1_440
    return day.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        minutes=minutes
    )


def _simulated_usage(
    *, index: int, rng: random.Random, daily_factor: float
) -> dict[str, object]:
    input_tokens = round(
        max(100, (650 + (index % 8) * 45 + rng.randint(0, 30)) * daily_factor)
    )
    output_tokens = round(
        max(40, (110 + (index % 5) * 18 + rng.randint(0, 12)) * daily_factor)
    )
    cached_input_tokens = min(
        input_tokens, round((200 + (index % 4) * 25) * daily_factor)
    )
    return {
        'input_tokens': input_tokens,
        'input_tokens_details': {'cached_tokens': cached_input_tokens},
        'output_tokens': output_tokens,
        'total_tokens': input_tokens + output_tokens,
    }


async def _simulate(
    *,
    cases: list[GoldenCase],
    dataset_path: Path,
    corpus_root: Path,
    mode: SearchMode,
    k: int,
    days: int,
    requests_per_day: int,
    error_rate: float,
    feedback_rate: float,
    variance: float,
    seed: int,
    simulate_usage: bool,
    model: str,
    clear_simulated: bool,
) -> int:
    rng = random.Random(seed)
    now = datetime.now(UTC)
    strategy = create_search_strategy(mode)
    client = FixtureLLMClient(dataset_path=dataset_path)
    total_requests = 0

    with (
        corpus_context(root=corpus_root, schema_name='public'),
        database_engine(schema_name='public') as engine,
    ):
        if clear_simulated:
            with engine.begin() as connection:
                simulated_request_ids = select(llm_usage_events.c.request_id).where(
                    llm_usage_events.c.metadata.op('->>')('simulated') == 'true'
                )
                connection.execute(
                    delete(rag_ratings).where(
                        rag_ratings.c.request_id.in_(simulated_request_ids)
                    )
                )
                connection.execute(
                    delete(rag_results).where(
                        rag_results.c.request_id.in_(simulated_request_ids)
                    )
                )
                connection.execute(
                    delete(llm_usage_events).where(
                        llm_usage_events.c.metadata.op('->>')('simulated') == 'true'
                    )
                )
        for day_index in range(days):
            daily_factor = rng.uniform(1 - variance, 1 + variance)
            requests_today = max(1, round(requests_per_day * daily_factor))
            rate_factor = rng.uniform(1 - variance, 1 + variance)
            daily_error_rate = min(1, error_rate * rate_factor)
            daily_feedback_rate = min(1, feedback_rate * rate_factor)
            for slot in range(requests_today):
                case = cases[total_requests % len(cases)]
                result = await answer_question_async(
                    case.question,
                    mode=mode,
                    k=k,
                    llm_client=client,
                    engine=engine,
                    strategy=strategy,
                )
                payload = result.to_dict()
                retrieval_latency = round(max(5, rng.gauss(35 * daily_factor, 8)))
                generation_latency = round(max(20, rng.gauss(260 * daily_factor, 55)))
                payload['retrieval_latency_ms'] = retrieval_latency
                payload['generation_latency_ms'] = generation_latency
                payload['total_latency_ms'] = retrieval_latency + generation_latency
                if rng.random() < daily_error_rate:
                    payload['success'] = False
                    payload['error'] = {
                        'stage': 'generation',
                        'type': 'SimulatedError',
                        'message': 'Synthetic dashboard traffic failure',
                    }
                    payload['generated']['answer'] = GENERATION_ERROR_ANSWER

                store_rag_result(result.request_id, payload, engine=engine)
                simulated_at = _simulated_timestamp(
                    now=now,
                    day_index=day_index,
                    slot=slot,
                    requests_per_day=requests_today,
                    days=days,
                )
                with engine.begin() as connection:
                    connection.execute(
                        update(rag_results)
                        .where(rag_results.c.request_id == result.request_id)
                        .values(created_at=simulated_at)
                    )
                    if simulate_usage:
                        usage_event = _usage_event_values(
                            request_id=result.request_id,
                            rag_run_id=None,
                            judge_run_id=None,
                            call_type='answer',
                            provider='openai',
                            model=model,
                            usage=_simulated_usage(
                                index=total_requests,
                                rng=rng,
                                daily_factor=daily_factor,
                            ),
                            connection=connection,
                        )
                        assert usage_event is not None
                        usage_event['metadata'] = {
                            'simulated': True,
                            'source': 'tools/simulate_rag_traffic.py',
                        }
                        connection.execute(
                            insert(llm_usage_events).values(
                                **usage_event,
                                created_at=simulated_at,
                            )
                        )
                    if rng.random() < daily_feedback_rate:
                        connection.execute(
                            insert(rag_ratings).values(
                                request_id=result.request_id,
                                helpful=rng.random() >= 0.2,
                                comment='Synthetic dashboard feedback',
                                created_at=simulated_at,
                            )
                        )
                total_requests += 1
    return total_requests


def main() -> None:
    """Generate deterministic traffic from the golden dataset."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument('--mode', choices=tuple(mode.value for mode in SearchMode))
    parser.add_argument('--k', type=int, default=5)
    parser.add_argument('--days', type=int, default=14)
    parser.add_argument('--requests-per-day', type=int, default=20)
    parser.add_argument('--error-rate', type=float, default=0.05)
    parser.add_argument('--feedback-rate', type=float, default=0.35)
    parser.add_argument(
        '--variance',
        type=float,
        default=0.35,
        help='Relative daily variation for volume, rates, tokens, and latency (0-1).',
    )
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--model', default='gpt-4.1-mini')
    parser.add_argument(
        '--clear-simulated',
        action='store_true',
        help='Remove prior rows generated by this simulator before inserting new data.',
    )
    parser.add_argument(
        '--no-simulated-usage',
        action='store_true',
        help='Only persist RAG results and feedback, without synthetic cost events.',
    )
    args = parser.parse_args()

    if args.days <= 0 or args.requests_per_day <= 0 or args.k <= 0:
        parser.error('days, requests-per-day, and k must be greater than zero')
    if (
        not 0 <= args.error_rate <= 1
        or not 0 <= args.feedback_rate <= 1
        or not 0 <= args.variance <= 1
    ):
        parser.error(
            'error-rate, feedback-rate, and variance must be between zero and one'
        )

    cases = load_golden_dataset(root=args.dataset)
    if not cases:
        parser.error('the golden dataset contains no cases')
    total = asyncio.run(
        _simulate(
            cases=cases,
            dataset_path=golden_dataset_path(root=args.dataset),
            corpus_root=args.corpus,
            mode=SearchMode(args.mode or DEFAULT_SEARCH_MODE.value),
            k=args.k,
            days=args.days,
            requests_per_day=args.requests_per_day,
            error_rate=args.error_rate,
            feedback_rate=args.feedback_rate,
            variance=args.variance,
            seed=args.seed,
            simulate_usage=not args.no_simulated_usage,
            model=args.model,
            clear_simulated=args.clear_simulated,
        )
    )
    print(f'Simulated {total} RAG requests in the public schema.')


if __name__ == '__main__':
    main()
