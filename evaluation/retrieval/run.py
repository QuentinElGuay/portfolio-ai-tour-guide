"""Standalone retrieval benchmark runner."""

import argparse
import json
from pathlib import Path

from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, corpus_context
from ai_tour_guide.knowledge_base.retrieval import retrieve
from ai_tour_guide.knowledge_base.search import SearchMode
from evaluation.dataset import DEFAULT_DATASET_ROOT, GoldenCase, load_golden_dataset
from evaluation.retrieval.metrics import (
    hit_rate_at_k,
    recall_at_k,
    reciprocal_rank,
)

DEFAULT_K = 5
SEARCH_MODES = tuple(SearchMode)


def _evidence_key(
    source_url: str,
    version: str | None,
    section_path: tuple[str, ...],
    page: int,
) -> str:
    return json.dumps([source_url, version, section_path, page], ensure_ascii=False)


def _expected_evidence(case: GoldenCase) -> set[str]:
    evidence: set[str] = set()
    for source in case.expected.relevant_sources:
        paths = source.section_paths or ((),)
        for section_path in paths:
            for page in source.pages:
                evidence.add(
                    _evidence_key(source.source_url, source.version, section_path, page)
                )
    return evidence


def _retrieved_evidence(result: object) -> list[str]:
    source = result.source
    if source.page_start is None or source.page_end is None:
        return []
    return [
        _evidence_key(
            source.source_url,
            source.version,
            source.section_path,
            page,
        )
        for page in range(source.page_start, source.page_end + 1)
    ]


def _case_metrics(case: GoldenCase, mode: SearchMode, *, k: int) -> dict[str, object]:
    expected = _expected_evidence(case)
    retrieved = retrieve(case.question, mode=mode, k=k)
    retrieved_evidence = [
        evidence for result in retrieved for evidence in _retrieved_evidence(result)
    ]
    # A page-spanning chunk can produce duplicate evidence keys; preserve rank order.
    deduplicated = list(dict.fromkeys(retrieved_evidence))
    return {
        'id': case.case_id,
        'category': case.category,
        'hit_rate_at_k': hit_rate_at_k(deduplicated, expected, k=k),
        'recall_at_k': recall_at_k(deduplicated, expected, k=k),
        'reciprocal_rank': reciprocal_rank(deduplicated, expected),
        'retrieved_chunks': [result.source.chunk_id for result in retrieved],
    }


def run(
    *,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
) -> None:
    """Run retrieval evaluation over one corpus and one golden dataset."""
    cases = load_golden_dataset(root=dataset_root)

    with corpus_context(root=corpus_root, schema_name='evaluation'):
        report: dict[str, object] = {
            'dataset': str(dataset_root),
            'corpus': str(corpus_root),
            'k': DEFAULT_K,
            'cases': len(cases),
            'modes': {},
        }
        for mode in SEARCH_MODES:
            case_results = [_case_metrics(case, mode, k=DEFAULT_K) for case in cases]
            report['modes'][mode.value] = {
                'hit_rate_at_k': _mean(case['hit_rate_at_k'] for case in case_results),
                'recall_at_k': _mean(case['recall_at_k'] for case in case_results),
                'mean_reciprocal_rank': _mean(
                    case['reciprocal_rank'] for case in case_results
                ),
                'cases': case_results,
            }
    print(json.dumps(report, indent=2, ensure_ascii=False))


def _mean(values: object) -> float:
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
