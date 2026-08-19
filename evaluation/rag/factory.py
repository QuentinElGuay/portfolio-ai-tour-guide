"""Provider selection for evaluation judges."""

from typing import Protocol

from ai_tour_guide.agent.llm.clients import LLMProvider
from evaluation.dataset import GoldenCase
from evaluation.rag.judge import JudgesSettings, JudgeVerdict, OpenAIAnswerJudge


class AnswerJudge(Protocol):
    model: str

    async def judge(self, case: GoldenCase, answer: str) -> JudgeVerdict: ...


class JudgeFactory:
    """Create an answer judge for a named LLM provider."""

    @staticmethod
    def create(settings: JudgesSettings) -> AnswerJudge:

        if not settings.api_key.get_secret_value().strip():
            raise ValueError('An LLM API key must be provided.')

        match settings.llm_provider:
            case LLMProvider.OPENAI:
                return OpenAIAnswerJudge(settings)


__all__ = ['AnswerJudge', 'JudgeFactory']
