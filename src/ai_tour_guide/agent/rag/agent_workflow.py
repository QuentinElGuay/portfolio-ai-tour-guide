"""Bounded LangGraph workflow for source-grounded live answers."""

from typing import Literal, NotRequired, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.chat.models import Message, Role
from ai_tour_guide.agent.llm.clients import AgentLLMClient
from ai_tour_guide.agent.rag.models import GeneratedAnswer
from ai_tour_guide.agent.rag.prompting import build_messages
from ai_tour_guide.knowledge_base.retrieval.context import retrieve_context
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search import DEFAULT_SEARCH_MODE
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy

MAX_SEARCH_CALLS = 2
SEARCH_K = 5


class AgentState(TypedDict):
    question: str
    queries: list[str]
    contexts: tuple[RetrievedContext, ...]
    next_query: str | None
    messages: NotRequired[tuple[Message, ...]]
    generated: NotRequired[GeneratedAnswer]
    retrieval_error: NotRequired[Exception]


def build_agent_graph(
    llm_client: AgentLLMClient,
    *,
    engine: Engine | None,
    strategy: SearchStrategy | None,
):
    """Compile the live, source-grounded search-decision workflow."""

    async def decide(state: AgentState) -> dict[str, object]:
        query = await llm_client.choose_search_query(
            state['question'],
            previous_queries=tuple(state['queries']),
            has_context=bool(state['contexts']),
        )
        return {'next_query': query}

    def route_after_decision(
        state: AgentState,
    ) -> Literal['search', 'generate', 'insufficient']:
        if state['next_query'] is not None and len(state['queries']) < MAX_SEARCH_CALLS:
            return 'search'
        return (
            'generate' if state['contexts'] or not state['queries'] else 'insufficient'
        )

    def search(state: AgentState) -> dict[str, object]:
        query = state['next_query']
        if query is None:
            return {}
        try:
            contexts = retrieve_context(
                query,
                search_mode=DEFAULT_SEARCH_MODE,
                k=SEARCH_K,
                engine=engine,
                strategy=strategy,
            )
        except (OSError, SQLAlchemyError) as exc:
            return {'retrieval_error': exc}
        return {
            'queries': [*state['queries'], query],
            'contexts': (*state['contexts'], *contexts),
            'next_query': None,
        }

    def route_after_search(
        state: AgentState,
    ) -> Literal['decide', 'insufficient']:
        return 'insufficient' if 'retrieval_error' in state else 'decide'

    async def generate(state: AgentState) -> dict[str, object]:
        messages = (
            build_messages(state['question'], state['contexts'])
            if state['contexts']
            else _build_meta_messages(state['question'])
        )
        return {
            'messages': messages,
            'generated': await llm_client.answer_question(messages),
        }

    def insufficient(state: AgentState) -> dict[str, object]:
        return {}

    graph = StateGraph(AgentState)
    graph.add_node('decide', decide)
    graph.add_node('search', search)
    graph.add_node('generate', generate)
    graph.add_node('insufficient', insufficient)
    graph.add_edge(START, 'decide')
    graph.add_conditional_edges('decide', route_after_decision)
    graph.add_conditional_edges('search', route_after_search)
    graph.add_edge('generate', END)
    graph.add_edge('insufficient', END)
    return graph.compile()


async def run_agent_workflow(
    question: str,
    llm_client: AgentLLMClient,
    *,
    engine: Engine | None = None,
    strategy: SearchStrategy | None = None,
) -> AgentState:
    """Run the bounded graph and return its complete execution state."""
    graph = build_agent_graph(llm_client, engine=engine, strategy=strategy)
    return cast(
        AgentState,
        await graph.ainvoke(
            {'question': question, 'queries': [], 'contexts': (), 'next_query': None}
        ),
    )


def _build_meta_messages(question: str) -> tuple[Message, ...]:
    return (
        Message(
            role=Role.SYSTEM,
            content=(
                'You are Baguette Voyages’ assistant. Answer only conversational or '
                'meta questions about the assistant and its capabilities. Do not answer '
                'tourism facts without retrieved source context. Return structured JSON '
                'with `answer`, `citations`, and `emotion`; citations must be empty.'
            ),
        ),
        Message(role=Role.USER, content=question),
    )
