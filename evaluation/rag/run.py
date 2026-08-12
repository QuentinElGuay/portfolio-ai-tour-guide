"""Standalone RAG benchmark runner."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, corpus_context
from evaluation.dataset import DEFAULT_DATASET_ROOT, load_golden_dataset


def run(
    *,
    corpus_version: int,
    dataset_version: int,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
) -> None:
    """Run end-to-end RAG evaluation over one corpus and golden dataset."""
    cases = load_golden_dataset(dataset_version, root=dataset_root)

    with corpus_context(corpus_version, root=corpus_root):
        # TODO: Extend GoldenCase with generation expectations after that schema
        # is decided, then wire the RAG pipeline and evaluator here.
        raise NotImplementedError(
            f"TODO: RAG evaluation runner ({len(cases)} golden cases loaded)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG over a fixed corpus.")
    parser.add_argument("--corpus-version", type=int, required=True)
    parser.add_argument("--dataset-version", type=int, required=True)
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    args = parser.parse_args()
    run(
        corpus_version=args.corpus_version,
        dataset_version=args.dataset_version,
        corpus_root=args.corpus_root,
        dataset_root=args.dataset_root,
    )


if __name__ == "__main__":
    main()
