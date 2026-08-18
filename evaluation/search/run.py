"""Standalone search benchmark runner."""

import argparse
import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session
from tqdm import tqdm

from ai_tour_guide.knowledge_base import slugify_section_path
from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, corpus_context
from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentRow
from ai_tour_guide.knowledge_base.search import SearchMode, SearchResult
from ai_tour_guide.knowledge_base.search.strategies import (
    HybridSearchStrategy,
    SearchStrategy,
    VectorSearchStrategy,
    create_search_strategy,
)
from evaluation.dataset import (
    DEFAULT_DATASET_ROOT,
    GoldenCase,
    load_golden_dataset,
)
from evaluation.metrics import mean
from evaluation.search.metrics import (
    hit_rate_at_k,
    recall_at_k,
    reciprocal_rank,
)

DEFAULT_K = 5
SEARCH_MODES = tuple(SearchMode)


class SearchResultTrace(TypedDict):
    """Diagnostic fields retained for one raw ranked search result."""

    rank: int
    score: float
    score_kind: str
    chunk_id: str
    document_id: int
    source_url: str
    version: str | None
    section_path: tuple[str, ...]


class CaseMetrics(TypedDict):
    """Metrics and diagnostics calculated for one evaluated question."""

    id: int
    category: str
    search_latency_ms: float
    raw_hit_rate_at_k: float
    raw_recall_at_k: float
    raw_reciprocal_rank: float
    results: list[SearchResultTrace]


def _evidence_key(
    source_url: str,
    version: str | None,
    section_path: tuple[str, ...],
) -> str:
    return json.dumps([source_url, version, section_path], ensure_ascii=False)


def _expected_evidence(case: GoldenCase) -> tuple[str, ...]:
    source = case.expected.relevant_source
    return (_evidence_key(source.source_url, source.version, source.section_path),)


def _section_evidence_key(result: SearchResult) -> str:
    """Return the golden-dataset section identity for one search result."""
    source_document = result.document
    return _evidence_key(
        source_document.source_url,
        source_document.version,
        slugify_section_path(list(result.chunk.section_path[:-1])),
    )


def _raw_evidence(results: Iterable[SearchResult]) -> list[str]:
    """Return one section evidence key per raw ranked search result."""
    return [_section_evidence_key(result) for result in results]


def _trace(result: SearchResult) -> SearchResultTrace:
    """Preserve raw search diagnostics for optional detailed reporting."""
    return {
        'rank': result.search.rank,
        'score': result.search.score,
        'score_kind': result.search.score_kind.value,
        'chunk_id': result.chunk.chunk_id,
        'document_id': result.document.document_id,
        'source_url': result.document.source_url,
        'version': result.document.version,
        'section_path': tuple(result.chunk.section_path),
    }


def _case_metrics(
    session: Session,
    strategy: SearchStrategy,
    case: GoldenCase,
    *,
    k: int,
) -> CaseMetrics:
    """Evaluate raw chunk ranking for one golden case."""
    expected = _expected_evidence(case)
    started = perf_counter()
    results = strategy.search(session, case.question, k=k)
    search_latency_ms = (perf_counter() - started) * 1000
    raw_evidence = _raw_evidence(results)

    return {
        'id': case.case_id,
        'category': case.category,
        'search_latency_ms': search_latency_ms,
        'raw_hit_rate_at_k': hit_rate_at_k(raw_evidence, expected, k=k),
        'raw_recall_at_k': recall_at_k(raw_evidence, expected, k=k),
        'raw_reciprocal_rank': reciprocal_rank(raw_evidence, expected),
        'results': [_trace(result) for result in results],
    }


def run(
    *,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    k: int = DEFAULT_K,
    modes: Iterable[SearchMode] = SEARCH_MODES,
) -> None:
    """Run search evaluation over one corpus and one golden dataset."""
    if k <= 0:
        raise ValueError('k must be greater than zero')
    cases = [
        case
        for case in load_golden_dataset(root=dataset_root)
        if case.expected.answerable
    ]
    selected_modes = tuple(SearchMode(mode) for mode in modes)

    with (
        corpus_context(root=corpus_root, schema_name='evaluation'),
        database_engine(schema_name='evaluation') as engine,
    ):
        report: dict[str, Any] = {
            'dataset': str(dataset_root),
            'corpus': str(corpus_root),
            'schema': 'evaluation',
            'k': k,
            'cases': len(cases),
            'modes': {},
        }
        with Session(engine) as session:
            session.connection()
            if session.scalar(select(DocumentRow.document_id).limit(1)) is None:
                raise RuntimeError(
                    'The evaluation schema is empty. Run `make evaluate` after '
                    'loading a corpus.'
                )
            for mode in selected_modes:
                strategy = create_search_strategy(mode)
                case_results = [
                    _case_metrics(session, strategy, case, k=k)
                    for case in tqdm(
                        cases,
                        desc=f'Search ({mode.value})',
                        unit='case',
                    )
                ]
                report['modes'][mode.value] = {
                    'configuration': _strategy_configuration(strategy),
                    'chunk_ranking': {
                        'hit_rate_at_k': mean(
                            case['raw_hit_rate_at_k'] for case in case_results
                        ),
                        'recall_at_k': mean(
                            case['raw_recall_at_k'] for case in case_results
                        ),
                        'mean_reciprocal_rank': mean(
                            case['raw_reciprocal_rank'] for case in case_results
                        ),
                    },
                    'mean_search_latency_ms': mean(
                        case['search_latency_ms'] for case in case_results
                    ),
                }
    print(json.dumps(report, indent=2, ensure_ascii=False))


def _strategy_configuration(strategy: SearchStrategy) -> dict[str, object]:
    """Return reproducibility information for the active search strategy."""
    configuration: dict[str, object] = {'strategy': type(strategy).__name__}
    if isinstance(strategy, VectorSearchStrategy):
        configuration['embedding'] = asdict(strategy.embedder.metadata)
    if isinstance(strategy, HybridSearchStrategy):
        configuration['hybrid'] = {
            'vector_weight': strategy.settings.vector_weight,
            'text_weight': strategy.settings.text_weight,
            'rank_constant': strategy.settings.rank_constant,
        }
        if isinstance(strategy.vector, VectorSearchStrategy):
            configuration['embedding'] = asdict(strategy.vector.embedder.metadata)
    return configuration


def main() -> None:
    parser = argparse.ArgumentParser(description='Evaluate ranked search results.')
    parser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument('--k', type=int, default=DEFAULT_K)
    parser.add_argument(
        '--mode',
        type=SearchMode,
        choices=SEARCH_MODES,
        action='append',
        help='Evaluate one mode; repeat to evaluate several modes. Defaults to all.',
    )
    args = parser.parse_args()
    run(
        corpus_root=args.corpus,
        dataset_root=args.dataset,
        k=args.k,
        modes=args.mode or SEARCH_MODES,
    )


if __name__ == '__main__':
    main()
