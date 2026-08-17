import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from openai import AsyncOpenAI
from pydantic import SecretStr

PROJECT_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.dataset import ExpectedOutcome, GoldenCase, SourceExpectation
from evaluation.rag.judge import JudgeSettings, JudgeVerdict, OpenAIAnswerJudge
from evaluation.rag.metrics import summarize_judgements


def _case() -> GoldenCase:
    return GoldenCase(
        case_id=1,
        question='What are typical summer temperatures?',
        category='climate',
        expected=ExpectedOutcome(
            answerable=True,
            reference_answer='Typical summer temperatures range from 18°C to 24°C.',
            relevant_sources=(
                SourceExpectation(
                    source_url='https://example.test/guide',
                    version=None,
                    section_path=('guide', 'climate'),
                ),
            ),
        ),
    )


def test_judge_settings_prefer_dedicated_values(monkeypatch) -> None:
    monkeypatch.setenv('AGENT_OPENAI_API_KEY', 'agent-key')
    monkeypatch.setenv('AGENT_OPENAI_MODEL', 'agent-model')
    monkeypatch.setenv('EVALUATION_OPENAI_JUDGE_API_KEY', 'judge-key')
    monkeypatch.setenv('EVALUATION_OPENAI_JUDGE_MODEL', 'judge-model')

    settings = JudgeSettings()

    assert settings.api_key.get_secret_value() == 'judge-key'
    assert settings.model == 'judge-model'


def test_judge_sends_reference_answer_and_returns_structured_verdict() -> None:
    response = SimpleNamespace(
        output_text='{"correct": true, "reason": "The temperatures match."}'
    )
    client = MagicMock()
    client.responses.create = AsyncMock(return_value=response)
    judge = OpenAIAnswerJudge(
        JudgeSettings(api_key=SecretStr('test-key'), model='judge-model'),
        client=cast(AsyncOpenAI, client),
    )

    verdict = asyncio.run(
        judge.judge(_case(), 'Summer temperatures are usually 18°C to 24°C.')
    )

    assert verdict.correct is True
    assert verdict.reason == 'The temperatures match.'
    assert client.responses.create.await_args is not None
    request = client.responses.create.await_args.kwargs
    payload = json.loads(request['input'][1]['content'])
    assert payload['reference_answer'] == (
        'Typical summer temperatures range from 18°C to 24°C.'
    )
    assert (
        payload['candidate_answer'] == 'Summer temperatures are usually 18°C to 24°C.'
    )
    assert request['text']['format']['type'] == 'json_schema'


def test_summarize_judgements_reports_correctness_and_latency() -> None:
    correct = JudgeVerdict(correct=True, reason='reason', latency_ms=20.0)
    incorrect = JudgeVerdict(correct=False, reason='reason', latency_ms=40.0)

    report = summarize_judgements([correct, incorrect])

    assert report == {
        'cases': 2,
        'answer_correct_rate': 0.5,
        'mean_judge_latency_ms': 30.0,
    }
