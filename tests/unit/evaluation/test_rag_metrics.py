import sys
from datetime import date
from pathlib import Path

from ai_tour_guide.app.agent.responses import INSUFFICIENT_CONTEXT_ANSWER
from ai_tour_guide.app.services.rag.models import (
    CitationInvalidReason,
    GeneratedAnswer,
    InvalidCitation,
    LLMCitation,
    RAGResult,
    SourceReference,
)
from ai_tour_guide.knowledge_base.search import SearchMode

PROJECT_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.dataset import ExpectedOutcome, GoldenCase, SourceExpectation
from evaluation.rag.metrics import score_case, summarize


def _case(*, answerable: bool = True) -> GoldenCase:
    return GoldenCase(
        case_id=1,
        question='What is this?',
        category='test',
        expected=ExpectedOutcome(
            answerable=answerable,
            reference_answer='An answer',
            relevant_source=SourceExpectation(
                source_url='https://example.test/guide',
                version='2026',
                section_path=('guide', 'activities'),
            ),
        ),
    )


def _result(
    *,
    answer: str = 'An answer',
    invalid: tuple[InvalidCitation, ...] = (),
    section_paths: tuple[tuple[tuple[str, ...], ...], ...] = (
        (('Guide', 'Activities', 'Details'),),
    ),
) -> RAGResult:
    return RAGResult(
        question='What is this?',
        mode=SearchMode.VECTOR,
        k=5,
        messages=(),
        generated=GeneratedAnswer(
            answer,
            citations=(LLMCitation('https://example.test/guide', '2026', None, None),),
        ),
        sources=(
            SourceReference(
                source_url='https://example.test/guide',
                version='2026',
                title='Guide',
                publisher=None,
                collection=None,
                publication_date=date(2026, 1, 1),
            ),
        ),
        invalid_citations=invalid,
        citation_section_paths=section_paths,
    )


def test_score_case_matches_sources_and_normalized_sections() -> None:
    """Verify that score case matches sources and normalized sections."""
    metrics = score_case(_case(), _result())

    assert metrics.source_precision == 1.0
    assert metrics.source_recall == 1.0
    assert metrics.section_precision == 1.0
    assert metrics.section_recall == 1.0
    assert metrics.citation_validity == 1.0
    assert metrics.refusal_correct is True


def test_score_case_counts_invalid_citations_and_refusal() -> None:
    """Verify that score case counts invalid citations and refusal."""
    invalid = (
        InvalidCitation(
            source_url='https://other.test',
            version=None,
            page_start=1,
            page_end=1,
            reason=CitationInvalidReason.UNKNOWN_DOCUMENT,
        ),
    )
    metrics = score_case(
        _case(answerable=False),
        _result(answer=INSUFFICIENT_CONTEXT_ANSWER, invalid=invalid, section_paths=()),
    )

    assert metrics.citation_validity == 0.0
    assert metrics.refused is True
    assert metrics.refusal_correct is True
    assert metrics.section_recall == 0.0


def test_summarize_aggregates_case_metrics() -> None:
    """Verify that summarize aggregates case metrics."""
    report = summarize([score_case(_case(), _result())])

    assert report['cases'] == 1
    assert report['source_recall'] == 1.0
    assert report['refusal_accuracy'] == 1.0
