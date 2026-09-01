"""Session-scoped conversation orchestration around the RAG agent."""

from typing import Annotated, NotRequired, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy import Engine

from ai_tour_guide.agent.chat.models import Message, Role
from ai_tour_guide.agent.llm.clients import AgentLLMClient
from ai_tour_guide.agent.rag.models import RAGResult
from ai_tour_guide.agent.rag.pipeline import answer_question_async
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy


class ConversationState(TypedDict):
    """State retained for one conversation thread."""

    messages: Annotated[list[Message], add_messages]
    question: str
    resolved_question: str
    result: NotRequired[RAGResult]


def build_conversation_graph(
    llm_client: AgentLLMClient,
    *,
    engine: Engine | None,
    strategy: SearchStrategy | None,
    checkpointer: MemorySaver,
):
    """Build a session-memory graph that invokes the RAG graph as a sub-graph."""

    def resolve_question(state: ConversationState) -> dict[str, object]:
        previous_questions = [
            message['content']
            for message in state['messages'][:-1]
            if message['role'] in (Role.USER, 'user')
        ]
        question = state['question']
        if previous_questions and _is_follow_up(question):
            question = (
                f'{question}\n\nConversation context: the previous user question was '
                f'{previous_questions[-1]}'
            )
        return {'resolved_question': question}

    async def answer_with_rag(state: ConversationState) -> dict[str, object]:
        result = await answer_question_async(
            state['resolved_question'],
            llm_client=llm_client,
            engine=engine,
            strategy=strategy,
        )
        return {
            'result': result,
            'messages': [{'role': Role.ASSISTANT, 'content': result.answer}],
        }

    graph = StateGraph(ConversationState)
    graph.add_node('resolve_question', resolve_question)
    graph.add_node('rag_agent', answer_with_rag)
    graph.add_edge(START, 'resolve_question')
    graph.add_edge('resolve_question', 'rag_agent')
    graph.add_edge('rag_agent', END)
    return graph.compile(checkpointer=checkpointer)


def _is_follow_up(question: str) -> bool:
    words = set(question.casefold().replace('?', ' ').split())
    return bool(words & {'there', 'it', 'that', 'this', 'they', 'them', 'those'})


__all__ = ['ConversationState', 'build_conversation_graph']
