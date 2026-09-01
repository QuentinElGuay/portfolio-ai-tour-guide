"""Session-scoped conversation orchestration around the RAG agent."""

from collections.abc import Callable
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy import Engine

from ai_tour_guide.agent.flow import DEFAULT_FLOW_STEP, FlowStep
from ai_tour_guide.agent.llm.clients import AgentLLMClient
from ai_tour_guide.agent.rag.models import RAGResult
from ai_tour_guide.agent.rag.pipeline import answer_question_async
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy


class ConversationState(TypedDict):
    """State retained for one conversation thread."""

    messages: Annotated[list[BaseMessage], add_messages]
    flow_step: NotRequired[str]


def build_conversation_graph(
    llm_client: AgentLLMClient,
    *,
    engine: Engine | None,
    strategy: SearchStrategy | None,
    checkpointer: MemorySaver,
    on_result: Callable[[RAGResult], None],
    option_id: str | None = None,
):
    """Build the checkpointed graph used to answer one conversation turn."""

    async def answer_with_rag(state: ConversationState) -> dict[str, object]:
        """Resolve the current turn, run RAG, and append the assistant answer."""
        question = _resolve_question(state['messages'])
        flow_step = FlowStep(state.get('flow_step', DEFAULT_FLOW_STEP))
        result = await answer_question_async(
            question,
            llm_client=llm_client,
            engine=engine,
            strategy=strategy,
            option_id=option_id,
            flow_step=flow_step,
        )
        on_result(result)
        next_flow_step = result.retrieval_metadata.get('flow_step', flow_step.value)
        return {
            'messages': [AIMessage(content=result.answer)],
            'flow_step': str(next_flow_step),
        }

    graph = StateGraph(ConversationState)
    graph.add_node('rag_agent', answer_with_rag)
    graph.add_edge(START, 'rag_agent')
    graph.add_edge('rag_agent', END)
    return graph.compile(checkpointer=checkpointer)


def _resolve_question(messages: list[BaseMessage]) -> str:
    """Return the latest question, adding the prior question for follow-ups."""
    questions = (
        message.content
        for message in reversed(messages)
        if isinstance(message, HumanMessage) and isinstance(message.content, str)
    )
    question = next(questions, None)
    if question is None:
        raise RuntimeError('The conversation does not contain a user question.')
    previous_question = next(questions, None)
    if previous_question is not None and _is_follow_up(question):
        return (
            f'{question}\n\nConversation context: the previous user question was '
            f'{previous_question}'
        )
    return question


def _is_follow_up(question: str) -> bool:
    """Return whether a question contains a pronoun suggesting prior context."""
    words = set(question.casefold().replace('?', ' ').split())
    return bool(words & {'there', 'it', 'that', 'this', 'they', 'them', 'those'})


__all__ = ['ConversationState', 'build_conversation_graph']
