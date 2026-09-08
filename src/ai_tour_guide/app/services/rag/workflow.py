"""Bounded LangGraph workflow for source-grounded live answers."""

import logging
import re
from collections.abc import Callable
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
    format_conversation_history,
    is_destination_catalog_question,
)
from ai_tour_guide.knowledge_base.retrieval.catalog import list_indexed_destinations
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.retrieval.tool import (
    RetrievalStatus,
    search_tourism_knowledge_base,
)
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy

MAX_SEARCH_CALLS = 2
SEARCH_K = 5

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    question: str
    conversation_history: tuple[Message, ...]
    option_id: str | None
    flow_step: str
    input_type: str
    queries: list[str]
    contexts: tuple[RetrievedContext, ...]
    next_query: str | None
    messages: NotRequired[tuple[Message, ...]]
    generated: NotRequired[GeneratedAnswer]
    retrieval_error: NotRequired[Exception]
    retrieval_status: NotRequired[str]
    low_confidence_retrieval: NotRequired[bool]
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
            conversation_history=state['conversation_history'],
        )
        logger.info(
            'rag.decision query=%r prior_query_count=%s has_context=%s',
            query,
            len(state['queries']),
            bool(state['contexts']),
        )
        return {'next_query': query}

    def identify(state: AgentState) -> dict[str, object]:
        option_id = normalize_option_id(state['option_id'])
        flow_step = flow_step_for_option(
            option_id, FlowStep(state.get('flow_step', DEFAULT_FLOW_STEP))
        )
        question = question_for_option_id(option_id) if option_id else state['question']
        identity_answer = _identity_answer_for(question or state['question'])
        logger.info(
            'rag.identify option_id=%s flow_step=%s input_type=%s identity_match=%s',
            option_id,
            flow_step.value,
            input_type_for_option(option_id),
            bool(identity_answer),
        )
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
        if state.get('low_confidence_retrieval'):
            route = 'insufficient'
        elif (
            state['next_query'] is not None and len(state['queries']) < MAX_SEARCH_CALLS
        ):
            route = 'search'
        elif state['contexts'] or not state['queries']:
            route = 'generate'
        else:
            route = (
                'fallback'
                if isinstance(llm_client, NoContextFallbackClient)
                else 'insufficient'
            )
        logger.info(
            'rag.route_after_decision route=%s query_count=%s context_count=%s '
            'has_next_query=%s low_confidence=%s',
            route,
            len(state['queries']),
            len(state['contexts']),
            state['next_query'] is not None,
            bool(state.get('low_confidence_retrieval')),
        )
        return route

    def search(state: AgentState) -> dict[str, object]:
        query = state['next_query']
        if query is None:
            return {}
        try:
            result = search_tourism_knowledge_base(
                query,
                engine=engine,
                strategy=strategy,
            )
        except (OSError, SQLAlchemyError) as exc:
            logger.warning(
                'rag.search_failed query=%r error_type=%s', query, type(exc).__name__
            )
            return {'retrieval_error': exc}
        if result.status is RetrievalStatus.ERROR:
            message = result.error.message if result.error is not None else ''
            logger.warning(
                'rag.search_failed query=%r error_type=retrieval_error', query
            )
            return {'retrieval_error': RuntimeError(message)}
        logger.info(
            'rag.search_completed query=%r status=%s context_count=%s',
            query,
            result.status.value,
            len(result.contexts),
        )
        return {
            'queries': [*state['queries'], query],
            'contexts': (*state['contexts'], *result.contexts),
            'next_query': None,
            'retrieval_status': result.status.value,
            'low_confidence_retrieval': (
                result.status is RetrievalStatus.LOW_CONFIDENCE
            ),
        }

    def route_after_search(
        state: AgentState,
    ) -> Literal['decide', 'insufficient']:
        route = (
            'insufficient'
            if 'retrieval_error' in state or state.get('low_confidence_retrieval')
            else 'decide'
        )
        logger.info(
            'rag.route_after_search route=%s retrieval_error=%s low_confidence=%s',
            route,
            'retrieval_error' in state,
            bool(state.get('low_confidence_retrieval')),
        )
        return route

    async def generate(state: AgentState) -> dict[str, object]:
        messages = (
            build_messages(
                state['question'],
                state['contexts'],
                conversation_history=state['conversation_history'],
            )
            if state['contexts']
            else _build_meta_messages(state['question'], state['conversation_history'])
        )
        logger.info(
            'rag.generate context_count=%s prompt_mode=%s',
            len(state['contexts']),
            'grounded' if state['contexts'] else 'meta',
        )
        return {
            'messages': messages,
            'generated': await llm_client.answer_question(messages),
        }

    async def fallback(state: AgentState) -> dict[str, object]:
        if not isinstance(llm_client, NoContextFallbackClient):
            return {}
        logger.info('rag.fallback reason=no_context_fallback_client')
        return {'generated': await llm_client.answer_without_context(state['question'])}

    def insufficient(state: AgentState) -> dict[str, object]:
        logger.info(
            'rag.insufficient query_count=%s context_count=%s low_confidence=%s '
            'retrieval_error=%s',
            len(state['queries']),
            len(state['contexts']),
            bool(state.get('low_confidence_retrieval')),
            'retrieval_error' in state,
        )
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
    knowledge_base_available: Callable[[], bool] | None = None,
    retrieval_enabled: bool = True,
    conversation_history: tuple[Message, ...] = (),
) -> AgentState:
    """Run the bounded graph and return its complete execution state."""
    option_id = normalize_option_id(option_id)
    history = tuple(conversation_history)
    identity_question = question_for_option_id(option_id) if option_id else None
    identity_answer = _identity_answer_for(identity_question or question)
    logger.info(
        'rag.workflow_started option_id=%s flow_step=%s retrieval_enabled=%s '
        'history_message_count=%s question=%r',
        option_id,
        flow_step.value,
        retrieval_enabled,
        len(history),
        question,
    )
    if identity_answer:
        logger.info('rag.workflow_short_circuit route=identity')
        return {
            'question': question,
            'conversation_history': history,
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
        logger.info('rag.workflow_short_circuit route=destination_catalog')
        destination_names = list_indexed_destinations(engine)
        return {
            'question': question,
            'conversation_history': history,
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

    if not retrieval_enabled:
        logger.info('rag.workflow_short_circuit route=meta_retrieval_disabled')
        messages = _build_meta_messages(question, history)
        return {
            'question': question,
            'conversation_history': history,
            'option_id': option_id,
            'flow_step': flow_step_for_option(option_id, flow_step).value,
            'input_type': input_type_for_option(option_id),
            'queries': [],
            'contexts': (),
            'next_query': None,
            'messages': messages,
            'generated': await llm_client.answer_question(messages),
            'retrieval_status': 'disabled',
        }

    if knowledge_base_available is not None and not knowledge_base_available():
        logger.info('rag.workflow_short_circuit route=meta_empty_knowledge_base')
        messages = _build_meta_messages(question, history)
        return {
            'question': question,
            'conversation_history': history,
            'option_id': option_id,
            'flow_step': flow_step_for_option(option_id, flow_step).value,
            'input_type': input_type_for_option(option_id),
            'queries': [],
            'contexts': (),
            'next_query': None,
            'messages': messages,
            'generated': await llm_client.answer_question(messages),
        }

    graph = build_agent_graph(llm_client, engine=engine, strategy=strategy)
    return cast(
        AgentState,
        await graph.ainvoke(
            {
                'question': question,
                'conversation_history': history,
                'option_id': option_id,
                'flow_step': flow_step.value,
                'input_type': input_type_for_option(option_id),
                'queries': [],
                'contexts': (),
                'next_query': None,
            }
        ),
    )


def _build_meta_messages(
    question: str, conversation_history: tuple[Message, ...] = ()
) -> tuple[Message, ...]:
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
        Message(
            role=Role.USER,
            content=(
                f'{format_conversation_history(conversation_history)}\n\n'
                f'Current user question:\n{question}'
            ),
        ),
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
