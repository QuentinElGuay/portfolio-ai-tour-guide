"""Standalone search benchmark runner."""

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypedDict

from tqdm import tqdm

from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, corpus_context
from ai_tour_guide.knowledge_base.search import SearchMode, SearchResult, search
from evaluation.dataset import (
    DEFAULT_DATASET_ROOT,
    GoldenCase,
    load_golden_dataset,
    slugify_section_path,
)
from evaluation.search.metrics import (
    hit_rate_at_k,
    recall_at_k,
    reciprocal_rank,
)

DEFAULT_K = 5
SEARCH_MODES = tuple(SearchMode)


class CaseMetrics(TypedDict):
    """Metrics and trace data for one evaluated question."""

    id: int
    category: str
    hit_rate_at_k: float
    recall_at_k: float
    reciprocal_rank: float
    retrieved_chunks: list[str]


def _evidence_key(
    source_url: str,
    version: str | None,
    section_path: tuple[str, ...],
) -> str:
    return json.dumps([source_url, version, section_path], ensure_ascii=False)


def _expected_evidence(case: GoldenCase) -> tuple[str, ...]:
    evidence: set[str] = set()
    for source in case.expected.relevant_sources:
        evidence.add(
            _evidence_key(source.source_url, source.version, source.section_path)
        )
    return tuple(sorted(evidence))


def _retrieved_evidence(
    results: Iterable[SearchResult],
) -> list[str]:
    """Return unique section evidence keys in raw search ranking order."""
    evidence: dict[str, None] = {}
    for result in results:
        source_document = result.document
        key = _evidence_key(
            source_document.source_url,
            source_document.version,
            slugify_section_path(list(result.chunk.section_path[:-1])),
        )
        evidence.setdefault(key, None)
    return list(evidence)


def _case_metrics(case: GoldenCase, search_mode: SearchMode, *, k: int) -> CaseMetrics:
    expected: tuple[str, ...] = _expected_evidence(case)
    results = search(
        case.question,
        mode=search_mode,
        k=k,
    )
    retrieved_evidence = _retrieved_evidence(results)
    return {
        'id': case.case_id,
        'category': case.category,
        'hit_rate_at_k': hit_rate_at_k(retrieved_evidence, expected, k=k),
        'recall_at_k': recall_at_k(retrieved_evidence, expected, k=k),
        'reciprocal_rank': reciprocal_rank(retrieved_evidence, expected),
        'retrieved_chunks': [result.chunk.chunk_id for result in results],
    }


def run(
    *,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
) -> None:
    """Run search evaluation over one corpus and one golden dataset."""
    cases = load_golden_dataset(root=dataset_root)

    with corpus_context(root=corpus_root, schema_name='evaluation'):
        report: dict[str, Any] = {
            'dataset': str(dataset_root),
            'corpus': str(corpus_root),
            'k': DEFAULT_K,
            'cases': len(cases),
            'modes': {},
        }
        for mode in SEARCH_MODES:
            case_results = [
                _case_metrics(case, mode, k=DEFAULT_K)
                for case in tqdm(
                    cases,
                    desc=f'Search ({mode.value})',
                    unit='case',
                )
            ]
            report['modes'][mode.value] = {
                'hit_rate_at_k': _mean(case['hit_rate_at_k'] for case in case_results),
                'recall_at_k': _mean(case['recall_at_k'] for case in case_results),
                'mean_reciprocal_rank': _mean(
                    case['reciprocal_rank'] for case in case_results
                ),
            }
    print(json.dumps(report, indent=2, ensure_ascii=False))


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Evaluate retrieval over a fixed corpus.'
    )
    parser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET_ROOT)
    args = parser.parse_args()
    run(
        corpus_root=args.corpus,
        dataset_root=args.dataset,
    )


if __name__ == '__main__':
    main()
