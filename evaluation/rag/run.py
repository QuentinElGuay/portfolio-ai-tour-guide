"""Standalone RAG benchmark runner."""

import argparse
import json
from pathlib import Path

from sqlalchemy import select
from tqdm import tqdm

from ai_tour_guide.agent.llm.factory import create_default_llm_client
from ai_tour_guide.agent.rag.pipeline import answer_question
from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, corpus_context
from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentRow
from ai_tour_guide.knowledge_base.search import SearchMode
from evaluation.dataset import DEFAULT_DATASET_ROOT, load_golden_dataset
from evaluation.rag.metrics import score_case, summarize

DEFAULT_K = 5


def run(
    *,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    mode: SearchMode = SearchMode.VECTOR,
    k: int = DEFAULT_K,
) -> None:
    """Run end-to-end RAG evaluation over one corpus and golden dataset."""
    if k <= 0:
        raise ValueError('k must be greater than zero')
    cases = load_golden_dataset(root=dataset_root)
    client = create_default_llm_client()
    if client is None:
        raise RuntimeError(
            'No LLM client is configured. Set the OpenAI settings before running '
            'the RAG evaluation.'
        )

    selected_mode = SearchMode(mode)
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

        case_metrics = []
        for case in tqdm(cases, desc=f'RAG ({selected_mode.value})', unit='case'):
            result = answer_question(
                case.question,
                mode=selected_mode,
                k=k,
                client=client,
                engine=engine,
            )
            case_metrics.append(score_case(case, result))

    report = {
        'dataset': str(dataset_root),
        'corpus': str(corpus_root),
        'schema': 'evaluation',
        'mode': selected_mode.value,
        'k': k,
        'metrics': summarize(case_metrics),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description='Evaluate RAG over a fixed corpus.')
    parser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument(
        '--mode',
        choices=tuple(mode.value for mode in SearchMode),
        default=SearchMode.VECTOR.value,
    )
    parser.add_argument('--k', type=int, default=DEFAULT_K)
    args = parser.parse_args()
    run(
        corpus_root=args.corpus,
        dataset_root=args.dataset,
        mode=SearchMode(args.mode),
        k=args.k,
    )


if __name__ == '__main__':
    main()
