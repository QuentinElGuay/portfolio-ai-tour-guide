"""Application orchestration for retrieval-augmented answers."""

import asyncio

from ai_tour_guide.agent.llm.factory import create_default_llm_client
from ai_tour_guide.agent.llm.interfaces import LLMClient
from ai_tour_guide.agent.rag.models import RAGResult
from ai_tour_guide.agent.rag.prompting import build_context, build_messages
from ai_tour_guide.agent.responses import LLM_CONFIGURATION_REQUIRED_ANSWER
from ai_tour_guide.knowledge_base.retrieval import SearchMode, retrieve

INSUFFICIENT_CONTEXT_ANSWER = (
    'The available sources do not contain enough information to answer that question.'
)


def answer_question(
    question: str,
    *,
    mode: SearchMode = 'vector',
    k: int = 5,
    client: LLMClient | None = None,
) -> RAGResult:
    """Retrieve context and generate a grounded answer for ``question``."""
    selected_client = client or create_default_llm_client()
    if selected_client is None:
        return RAGResult(
            answer=LLM_CONFIGURATION_REQUIRED_ANSWER,
            retrieved=[],
        )

    retrieved = retrieve(question, mode=mode, k=k)
    if not retrieved:
        return RAGResult(answer=INSUFFICIENT_CONTEXT_ANSWER, retrieved=[])

    messages = build_messages(
        question,
        build_context([result.chunk for result in retrieved]),
    )
    answer = asyncio.run(selected_client.generate_reply(messages))
    return RAGResult(
        answer=answer,
        retrieved=retrieved,
    )


__all__ = ['INSUFFICIENT_CONTEXT_ANSWER', 'answer_question']
