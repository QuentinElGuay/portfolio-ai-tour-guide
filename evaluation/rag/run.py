"""Standalone RAG benchmark runner."""

import argparse
from pathlib import Path

from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, corpus_context
from evaluation.dataset import DEFAULT_DATASET_ROOT, load_golden_dataset


def run(
    *,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
) -> None:
    """Run end-to-end RAG evaluation over one corpus and golden dataset."""
    cases = load_golden_dataset(root=dataset_root)

    with corpus_context(root=corpus_root):
        # TODO: Call answer_question() and score its detailed RAGResult trace.
        raise NotImplementedError(
            f'TODO: RAG evaluation runner ({len(cases)} golden cases loaded)'
        )


def main() -> None:
    parser = argparse.ArgumentParser(description='Evaluate RAG over a fixed corpus.')
    parser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET_ROOT)
    args = parser.parse_args()
    run(
        corpus_root=args.corpus,
        dataset_root=args.dataset,
    )


if __name__ == '__main__':
    main()
