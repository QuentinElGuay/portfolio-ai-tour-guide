"""Standalone RAG and answer-judge evaluation runners."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from tqdm import tqdm

from ai_tour_guide.agent.llm.clients import LLMProvider
from ai_tour_guide.agent.llm.factory import create_llm_client
from ai_tour_guide.agent.llm.settings import AgentsSettings
from ai_tour_guide.agent.rag.models import RAGResult
from ai_tour_guide.agent.rag.persistence import store_rag_result
from ai_tour_guide.agent.rag.pipeline import answer_question_async
from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, corpus_context
from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentRow
from ai_tour_guide.knowledge_base.search import DEFAULT_SEARCH_MODE, SearchMode
from ai_tour_guide.knowledge_base.search.strategies import create_search_strategy
from evaluation.dataset import DEFAULT_DATASET_ROOT, GoldenCase, load_golden_dataset
from evaluation.rag.factory import JudgeFactory
from evaluation.rag.judge import JudgesSettings
from evaluation.rag.metrics import score_case, summarize, summarize_judgements
from evaluation.rag.persistence import (
    store_rag_evaluation,
    store_rag_judgements,
)

DEFAULT_K = 5


async def _generate_results(
    *,
    corpus_root: Path,
    dataset_root: Path,
    mode: SearchMode,
    k: int,
    evaluation_run_id: UUID,
) -> tuple[list[GoldenCase], list[RAGResult]]:
    if k <= 0:
        raise ValueError('k must be greater than zero')
    cases = load_golden_dataset(root=dataset_root)
    client = create_llm_client(AgentsSettings())
    search_mode = SearchMode(mode)
    strategy = create_search_strategy(search_mode)

    with (
        corpus_context(root=corpus_root, schema_name='evaluation'),
        database_engine(schema_name='evaluation') as engine,
    ):
        with engine.connect() as connection:
            if connection.scalar(select(DocumentRow.document_id).limit(1)) is None:
                raise RuntimeError(
                    'The evaluation schema is empty. Run `make evaluate` after '
                    'loading a corpus.'
                )

        async def evaluate_case(index: int, case: GoldenCase):
            return index, await answer_question_async(
                case.question,
                mode=search_mode,
                k=k,
                llm_client=client,
                engine=engine,
                strategy=strategy,
            )

        results: list[RAGResult | None] = [None] * len(cases)
        tasks = [
            asyncio.create_task(evaluate_case(index, case))
            for index, case in enumerate(cases)
        ]
        with tqdm(
            total=len(tasks), desc=f'RAG ({search_mode.value})', unit='case'
        ) as progress:
            for completed in asyncio.as_completed(tasks):
                index, result = await completed
                store_rag_result(
                    result.request_id,
                    result.to_dict(),
                    engine=engine,
                    evaluation_run_id=evaluation_run_id,
                )
                results[index] = result
                progress.update()

    return cases, [result for result in results if result is not None]


def _base_report(
    *, dataset_root: Path, corpus_root: Path, mode: SearchMode, k: int
) -> dict[str, object]:
    return {
        'dataset': str(dataset_root),
        'corpus': str(corpus_root),
        'schema': 'evaluation',
        'mode': SearchMode(mode).value,
        'k': k,
    }


async def run_rag_async(
    *,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    mode: SearchMode = DEFAULT_SEARCH_MODE,
    k: int = DEFAULT_K,
) -> None:
    """Run deterministic RAG metrics without semantic answer judging."""
    rag_run_id = uuid4()
    cases, results = await _generate_results(
        corpus_root=corpus_root,
        dataset_root=dataset_root,
        mode=mode,
        k=k,
        evaluation_run_id=rag_run_id,
    )
    report = _base_report(
        dataset_root=dataset_root, corpus_root=corpus_root, mode=mode, k=k
    )
    case_metrics = [score_case(case, result) for case, result in zip(cases, results)]
    with database_engine(schema_name='evaluation') as engine:
        run_id = store_rag_evaluation(
            dataset_path=dataset_root,
            corpus_path=corpus_root,
            mode=SearchMode(mode).value,
            k=k,
            cases=cases,
            results=results,
            metrics=case_metrics,
            configuration={'evaluation': 'rag'},
            engine=engine,
            run_id=rag_run_id,
        )
    report['run_id'] = str(run_id)
    report['metrics'] = summarize(case_metrics)
    print(json.dumps(report, indent=2, ensure_ascii=False))


async def run_judge_async(
    *,
    llm_provider: LLMProvider,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    mode: SearchMode = DEFAULT_SEARCH_MODE,
    k: int = DEFAULT_K,
) -> None:
    """Run RAG generation and persist separate semantic judge results."""
    rag_run_id = uuid4()
    cases, results = await _generate_results(
        corpus_root=corpus_root,
        dataset_root=dataset_root,
        mode=mode,
        k=k,
        evaluation_run_id=rag_run_id,
    )
    judge = JudgeFactory.create(JudgesSettings(llm_provider=llm_provider))
    verdicts = await asyncio.gather(
        *(judge.judge(case, result.answer) for case, result in zip(cases, results))
    )
    case_metrics = [score_case(case, result) for case, result in zip(cases, results)]
    with database_engine(schema_name='evaluation') as engine:
        rag_run_id = store_rag_evaluation(
            dataset_path=dataset_root,
            corpus_path=corpus_root,
            mode=SearchMode(mode).value,
            k=k,
            cases=cases,
            results=results,
            metrics=case_metrics,
            configuration={'evaluation': 'rag', 'judge_provider': llm_provider.value},
            engine=engine,
            run_id=rag_run_id,
        )
        judge_run_id = uuid4()
        judge_run_id = store_rag_judgements(
            rag_run_id=rag_run_id,
            provider=llm_provider.value,
            model=judge.model,
            cases=cases,
            results=results,
            judgements=verdicts,
            configuration={'evaluation': 'judge'},
            engine=engine,
            run_id=judge_run_id,
        )
    report = _base_report(
        dataset_root=dataset_root, corpus_root=corpus_root, mode=mode, k=k
    )
    report['run_id'] = str(rag_run_id)
    report['rag_run_id'] = str(rag_run_id)
    report['judge_run_id'] = str(judge_run_id)
    report['judge'] = {
        'model': judge.model,
        'metrics': summarize_judgements(verdicts),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


def run_rag(
    *,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    mode: SearchMode = DEFAULT_SEARCH_MODE,
    k: int = DEFAULT_K,
) -> None:
    """Run RAG evaluation from synchronous callers."""
    asyncio.run(
        run_rag_async(
            corpus_root=corpus_root,
            dataset_root=dataset_root,
            mode=mode,
            k=k,
        )
    )


def run_judge(
    *,
    llm_provider: LLMProvider,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    mode: SearchMode = DEFAULT_SEARCH_MODE,
    k: int = DEFAULT_K,
) -> None:
    """Run judge evaluation from synchronous callers."""
    asyncio.run(
        run_judge_async(
            llm_provider=llm_provider,
            corpus_root=corpus_root,
            dataset_root=dataset_root,
            mode=mode,
            k=k,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description='Evaluate the RAG pipeline.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    def add_common_arguments(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS_ROOT)
        subparser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET_ROOT)
        subparser.add_argument(
            '--mode',
            choices=tuple(mode.value for mode in SearchMode),
            default=DEFAULT_SEARCH_MODE.value,
        )
        subparser.add_argument('--k', type=int, default=DEFAULT_K)

    rag_parser = subparsers.add_parser('rag', help='Run deterministic RAG metrics.')
    add_common_arguments(rag_parser)
    judge_parser = subparsers.add_parser('judge', help='Run LLM answer judging.')
    add_common_arguments(judge_parser)
    judge_parser.add_argument(
        '--provider',
        required=True,
        choices=tuple(provider.value for provider in LLMProvider),
    )
    args = parser.parse_args()
    if args.command == 'rag':
        run_rag(
            corpus_root=args.corpus,
            dataset_root=args.dataset,
            mode=SearchMode(args.mode),
            k=args.k,
        )
    else:
        run_judge(
            llm_provider=LLMProvider(args.provider),
            corpus_root=args.corpus,
            dataset_root=args.dataset,
            mode=SearchMode(args.mode),
            k=args.k,
        )


if __name__ == '__main__':
    main()
