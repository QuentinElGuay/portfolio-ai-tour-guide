"""Deterministic RAG evaluation metrics.

These metrics assess retrieval and citation behavior. They deliberately do not
score the semantic quality of an answer; that requires a human or judge model.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from ai_tour_guide.app.agent.rag.models import RAGResult
from ai_tour_guide.app.agent.responses import INSUFFICIENT_CONTEXT_ANSWER
from evaluation.dataset import GoldenCase, slugify_section_path
from evaluation.rag.judge import JudgeVerdict


@dataclass(frozen=True, slots=True)
class RAGCaseMetrics:
    """Deterministic measurements for one RAG answer."""

    source_precision: float
    source_recall: float
    section_precision: float
    section_recall: float
    citation_validity: float
    citation_coverage: float
    refused: bool
    refusal_correct: bool
    error: bool
    retrieval_latency_ms: float | None
    generation_latency_ms: float | None
    total_latency_ms: float | None


def score_case(case: GoldenCase, result: RAGResult) -> RAGCaseMetrics:
    """Score deterministic retrieval, citation, refusal, and latency behavior."""
    case_source = case.expected.relevant_source

    expected_sources = (
        {_source_key(case_source.source_url, case_source.version)}
        if case_source is not None
        else set()
    )
    actual_sources = {
        _source_key(source.source_url, source.version) for source in result.sources
    }

    expected_sections = (
        {
            (
                _source_key(case_source.source_url, case_source.version),
                case_source.section_path,
            )
        }
        if case_source is not None
        else set()
    )

    actual_sections = _citation_sections(result)

    citation_count = len(result.generated.citations)
    invalid_count = len(result.invalid_citations)
    valid_count = max(citation_count - invalid_count, 0)

    refused = result.answer.strip() == INSUFFICIENT_CONTEXT_ANSWER
    return RAGCaseMetrics(
        source_precision=_precision(actual_sources, expected_sources),
        source_recall=_recall(actual_sources, expected_sources),
        section_precision=_precision(actual_sections, expected_sections),
        section_recall=_recall(actual_sections, expected_sections),
        citation_validity=(valid_count / citation_count if citation_count else 1.0),
        citation_coverage=_recall(actual_sources, expected_sources),
        refused=refused,
        refusal_correct=(
            result.error is None and refused == (not case.expected.answerable)
        ),
        error=result.error is not None,
        retrieval_latency_ms=result.retrieval_latency_ms,
        generation_latency_ms=result.generation_latency_ms,
        total_latency_ms=result.total_latency_ms,
    )


def summarize(metrics: Iterable[RAGCaseMetrics]) -> dict[str, float | int | None]:
    """Aggregate case metrics into one report suitable for JSON serialization."""
    cases = list(metrics)
    if not cases:
        return {'cases': 0}

    return {
        'cases': len(cases),
        'source_precision': _mean(item.source_precision for item in cases),
        'source_recall': _mean(item.source_recall for item in cases),
        'section_precision': _mean(item.section_precision for item in cases),
        'section_recall': _mean(item.section_recall for item in cases),
        'citation_validity': _mean(item.citation_validity for item in cases),
        'citation_coverage': _mean(item.citation_coverage for item in cases),
        'refusal_rate': _mean(float(item.refused) for item in cases),
        'refusal_accuracy': _mean(float(item.refusal_correct) for item in cases),
        'error_rate': _mean(float(item.error) for item in cases),
        'mean_retrieval_latency_ms': _mean_optional(
            item.retrieval_latency_ms for item in cases
        ),
        'mean_generation_latency_ms': _mean_optional(
            item.generation_latency_ms for item in cases
        ),
        'mean_total_latency_ms': _mean_optional(
            item.total_latency_ms for item in cases
        ),
    }


def summarize_judgements(verdicts: Iterable[JudgeVerdict]) -> dict[str, float | int]:
    """Aggregate semantic answer-quality verdicts returned by the LLM judge."""
    values = list(verdicts)
    if not values:
        return {'cases': 0}
    return {
        'cases': len(values),
        'answer_correct_rate': _mean(float(verdict.correct) for verdict in values),
        'mean_judge_latency_ms': _mean(verdict.latency_ms for verdict in values),
    }


def _citation_sections(
    result: RAGResult,
) -> set[tuple[tuple[str, str | None], tuple[str, ...]]]:
    sections: set[tuple[tuple[str, str | None], tuple[str, ...]]] = set()
    for source, paths in zip(result.sources, result.citation_section_paths):
        identity = _source_key(source.source_url, source.version)
        sections.update(
            (identity, slugify_section_path(list(path[:-1]))) for path in paths
        )
    return sections


def _source_key(source_url: str, version: str | None) -> tuple[str, str | None]:
    return source_url, version


def _precision[T](actual: set[T], expected: set[T]) -> float:
    return len(actual & expected) / len(actual) if actual else float(not expected)


def _recall[T](actual: set[T], expected: set[T]) -> float:
    return len(actual & expected) / len(expected) if expected else float(not actual)


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _mean_optional(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return _mean(present) if present else None


__all__ = ['RAGCaseMetrics', 'score_case', 'summarize', 'summarize_judgements']
