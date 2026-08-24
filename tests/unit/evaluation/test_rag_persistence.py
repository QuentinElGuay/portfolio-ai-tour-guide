"""Tests for RAG-evaluation persistence tables and row construction."""

from uuid import uuid4

from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGResult
from ai_tour_guide.knowledge_base.database.tables.evaluation import (
    metadata,
    rag_evaluation_results,
    rag_evaluation_runs,
    rag_judge_results,
    rag_judge_runs,
)
from ai_tour_guide.knowledge_base.search import SearchMode
from evaluation.dataset import ExpectedOutcome, GoldenCase, SourceExpectation
from evaluation.rag.judge import JudgeVerdict
from evaluation.rag.metrics import RAGCaseMetrics
from evaluation.rag.persistence import _judge_values, _result_values


def test_rag_evaluation_tables_use_dedicated_metadata() -> None:
    assert rag_evaluation_runs.metadata is metadata
    assert rag_evaluation_results.metadata is metadata
    assert isinstance(rag_evaluation_runs.c.run_id.type, UUID)
    assert isinstance(rag_evaluation_runs.c.configuration.type, JSONB)
    assert isinstance(rag_evaluation_results.c.expected_section_path.type, ARRAY)
    assert {
        foreign_key.target_fullname
        for foreign_key in rag_evaluation_results.c.run_id.foreign_keys
    } == {'rag_evaluation_runs.run_id'}
    assert rag_evaluation_results.c.request_id.nullable is False
    assert {
        'answer_correct',
        'judge_model',
        'judge_latency_ms',
        'judge_reason',
        'judge_metadata',
    }.isdisjoint(rag_evaluation_results.c.keys())


def test_rag_judge_tables_link_judgements_to_rag_runs() -> None:
    assert rag_judge_runs.metadata is metadata
    assert rag_judge_results.metadata is metadata
    assert {
        foreign_key.target_fullname
        for foreign_key in rag_judge_runs.c.rag_run_id.foreign_keys
    } == {'rag_evaluation_runs.run_id'}
    assert {
        foreign_key.target_fullname
        for foreign_key in rag_judge_results.c.run_id.foreign_keys
    } == {'rag_judge_runs.run_id'}
    assert rag_judge_results.c.answer_correct.nullable is False


def test_rag_evaluation_results_are_unique_per_run_and_case() -> None:
    primary_key = rag_evaluation_results.primary_key
    assert [column.name for column in primary_key.columns] == ['run_id', 'case_id']


def test_rag_evaluation_row_keeps_expected_evidence_and_metrics() -> None:
    source = SourceExpectation(
        source_url='https://example.test/guide.pdf',
        version=None,
        section_path=('guide', 'coast'),
    )
    case = GoldenCase(
        case_id=7,
        question='Where is the coast?',
        category='geography',
        expected=ExpectedOutcome(True, 'The coast is in Brittany.', source),
    )
    result = RAGResult(
        question=case.question,
        mode=SearchMode.HYBRID,
        k=5,
        messages=(),
        generated=GeneratedAnswer('The coast is in Brittany.'),
    )
    metrics = RAGCaseMetrics(
        source_precision=1.0,
        source_recall=1.0,
        section_precision=1.0,
        section_recall=1.0,
        citation_validity=1.0,
        citation_coverage=1.0,
        refused=False,
        refusal_correct=True,
        error=False,
        retrieval_latency_ms=10.0,
        generation_latency_ms=20.0,
        total_latency_ms=30.0,
    )

    values = _result_values(uuid4(), case, result, metrics)

    assert values['case_id'] == 7
    assert values['expected_section_path'] == ['guide', 'coast']
    assert values['section_recall'] == 1.0
    assert values['request_id'] == result.request_id

    judge_values = _judge_values(
        uuid4(),
        case,
        result,
        JudgeVerdict(
            correct=True, reason='Supported by the reference answer.', latency_ms=25.0
        ),
    )
    assert judge_values['case_id'] == 7
    assert judge_values['answer_correct'] is True
    assert judge_values['judge_reason'] == 'Supported by the reference answer.'
