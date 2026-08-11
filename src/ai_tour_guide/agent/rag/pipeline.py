"""Application orchestration for retrieval-augmented answers."""

import asyncio

from ai_tour_guide.agent.chat.backends import ChatBackend, create_backend
from ai_tour_guide.agent.rag.models import RAGResult
from ai_tour_guide.agent.rag.prompting import build_context, build_messages
from ai_tour_guide.knowledge_base.retrieval import SearchMode, retrieve

INSUFFICIENT_CONTEXT_ANSWER = (
    'The available sources do not contain enough information to answer that question.'
)


def answer_question(
    question: str,
    *,
    mode: SearchMode = 'vector',
    k: int = 5,
    backend: ChatBackend | None = None,
) -> RAGResult:
    """Retrieve context and generate a grounded answer for ``question``."""
    chunks = retrieve(question, mode=mode, k=k)

    if not chunks:
        return RAGResult(answer=INSUFFICIENT_CONTEXT_ANSWER, chunks=[])

    messages = build_messages(question, build_context(chunks))
    selected_backend = backend or create_backend()
    answer = asyncio.run(selected_backend.reply(messages))
    return RAGResult(answer=answer, chunks=chunks)


__all__ = ['INSUFFICIENT_CONTEXT_ANSWER', 'answer_question']
