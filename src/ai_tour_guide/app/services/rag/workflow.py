"""Bounded LangGraph workflow for source-grounded live answers."""

import re
from typing import Literal, NotRequired, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.app.agent.flow import (
    DEFAULT_FLOW_STEP,
    FlowStep,
    flow_step_for_option,
    input_type_for_option,
)
from ai_tour_guide.app.agent.identity import (
    BON_VOYAGE_IDENTITY,
    IDENTITY_ANSWERS,
    PETIT_GUIDE_IDENTITY,
    PETIT_GUIDE_PERSONALITY,
)
from ai_tour_guide.app.chat.models import Message, Role
from ai_tour_guide.app.chat.navigation import (
    next_option_ids,
    normalize_option_id,
    question_for_option_id,
)
from ai_tour_guide.app.llm.clients import (
    AgentLLMClient,
    NoContextFallbackClient,
)
from ai_tour_guide.app.services.rag.models import GeneratedAnswer
from ai_tour_guide.app.services.rag.prompting import (
    build_messages,
    is_destination_catalog_question,
)
from ai_tour_guide.knowledge_base.retrieval.catalog import list_indexed_destinations
from ai_tour_guide.knowledge_base.retrieval.context import retrieve_context
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search import DEFAULT_SEARCH_MODE
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy

MAX_SEARCH_CALLS = 2
SEARCH_K = 5


class AgentState(TypedDict):
    question: str
    option_id: str | None
    flow_step: str
    input_type: str
    queries: list[str]
    contexts: tuple[RetrievedContext, ...]
    next_query: str | None
    messages: NotRequired[tuple[Message, ...]]
    generated: NotRequired[GeneratedAnswer]
    retrieval_error: NotRequired[Exception]
    identity_answer: NotRequired[str]
    next_option_ids: NotRequired[tuple[str, ...]]


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

    def identify(state: AgentState) -> dict[str, object]:
        option_id = normalize_option_id(state['option_id'])
        flow_step = flow_step_for_option(
            option_id, FlowStep(state.get('flow_step', DEFAULT_FLOW_STEP))
        )
        question = question_for_option_id(option_id) if option_id else state['question']
        identity_answer = _identity_answer_for(question or state['question'])
        return {
            'question': question or state['question'],
            'flow_step': flow_step.value,
            'input_type': input_type_for_option(option_id),
            'identity_answer': identity_answer,
            'next_option_ids': next_option_ids(option_id) if option_id else (),
        }

    def route_identity(state: AgentState) -> Literal['identity', 'decide']:
        return 'identity' if state.get('identity_answer') else 'decide'

    def answer_identity(state: AgentState) -> dict[str, object]:
        return {'generated': GeneratedAnswer(state.get('identity_answer', ''))}

    def route_after_decision(
        state: AgentState,
    ) -> Literal['search', 'generate', 'fallback', 'insufficient']:
        if state['next_query'] is not None and len(state['queries']) < MAX_SEARCH_CALLS:
            return 'search'
        if state['contexts'] or not state['queries']:
            return 'generate'
        return (
            'fallback'
            if isinstance(llm_client, NoContextFallbackClient)
            else 'insufficient'
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

    async def fallback(state: AgentState) -> dict[str, object]:
        if not isinstance(llm_client, NoContextFallbackClient):
            return {}
        return {'generated': await llm_client.answer_without_context(state['question'])}

    def insufficient(state: AgentState) -> dict[str, object]:
        return {}

    graph = StateGraph(AgentState)
    graph.add_node('identify', identify)
    graph.add_node('identity', answer_identity)
    graph.add_node('decide', decide)
    graph.add_node('search', search)
    graph.add_node('generate', generate)
    graph.add_node('fallback', fallback)
    graph.add_node('insufficient', insufficient)
    graph.add_edge(START, 'identify')
    graph.add_conditional_edges('identify', route_identity)
    graph.add_edge('identity', END)
    graph.add_conditional_edges('decide', route_after_decision)
    graph.add_conditional_edges('search', route_after_search)
    graph.add_edge('generate', END)
    graph.add_edge('fallback', END)
    graph.add_edge('insufficient', END)
    # RetrievedContext contains ORM objects and is intentionally runtime-only.
    # This graph can run inside the checkpointed conversation graph, so it must not
    # inherit that checkpointer.
    return graph.compile(checkpointer=False)


async def run_agent_workflow(
    question: str,
    llm_client: AgentLLMClient,
    *,
    option_id: str | None = None,
    flow_step: FlowStep = DEFAULT_FLOW_STEP,
    engine: Engine | None = None,
    strategy: SearchStrategy | None = None,
) -> AgentState:
    """Run the bounded graph and return its complete execution state."""
    option_id = normalize_option_id(option_id)
    identity_question = question_for_option_id(option_id) if option_id else None
    identity_answer = _identity_answer_for(identity_question or question)
    if identity_answer:
        return {
            'question': question,
            'option_id': option_id,
            'flow_step': flow_step_for_option(option_id, flow_step).value,
            'input_type': input_type_for_option(option_id),
            'queries': [],
            'contexts': (),
            'next_query': None,
            'messages': (),
            'generated': GeneratedAnswer(identity_answer),
            'identity_answer': identity_answer,
            'next_option_ids': next_option_ids(option_id) if option_id else (),
        }
    if is_destination_catalog_question(question):
        destination_names = list_indexed_destinations(engine)
        return {
            'question': question,
            'option_id': option_id,
            'flow_step': flow_step_for_option(option_id, flow_step).value,
            'input_type': input_type_for_option(option_id),
            'queries': [],
            'contexts': (),
            'next_query': None,
            'messages': (),
            'generated': GeneratedAnswer(
                'Our currently covered destinations are:\n'
                + '\n'.join(f'- {name}' for name in destination_names)
                if destination_names
                else 'No destinations are currently indexed.'
            ),
        }

    graph = build_agent_graph(llm_client, engine=engine, strategy=strategy)
    return cast(
        AgentState,
        await graph.ainvoke(
            {
                'question': question,
                'option_id': option_id,
                'flow_step': flow_step.value,
                'input_type': input_type_for_option(option_id),
                'queries': [],
                'contexts': (),
                'next_query': None,
            }
        ),
    )


def _build_meta_messages(question: str) -> tuple[Message, ...]:
    return (
        Message(
            role=Role.SYSTEM,
            content=(
                f'{PETIT_GUIDE_IDENTITY}\n\n{PETIT_GUIDE_PERSONALITY}\n\n'
                f'Use this Bon Voyage identity when relevant:\n{BON_VOYAGE_IDENTITY}\n\n'
                'Answer only conversational or meta questions about the assistant and its '
                'capabilities. Do not answer tourism facts without retrieved source '
                'context. Return structured JSON with `answer`, `citations`, and '
                '`emotion`; citations must be empty.'
            ),
        ),
        Message(role=Role.USER, content=question),
    )


def _identity_answer_for(question: str) -> str:
    """Return a configured identity answer while tolerating simple user phrasing."""
    normalized = re.sub(r'[^a-z0-9]+', ' ', question.casefold()).strip()
    for configured_question, answer in IDENTITY_ANSWERS.items():
        configured_normalized = re.sub(
            r'[^a-z0-9]+', ' ', configured_question.casefold()
        ).strip()
        if normalized == configured_normalized:
            return answer
    return ''
