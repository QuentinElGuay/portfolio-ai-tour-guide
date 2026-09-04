"""Session-scoped conversation orchestration around the RAG agent."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Literal, NotRequired, TypedDict
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy import Engine

from ai_tour_guide.app.agent.flow import (
    DEFAULT_FLOW_STEP,
    FLOW_QUESTIONS,
    FlowStep,
    flow_definition,
    transition_for,
)
from ai_tour_guide.app.agent.identity import IDENTITY_ANSWERS, WELCOME_MESSAGE
from ai_tour_guide.app.agent.responses import EMPTY_KNOWLEDGE_BASE_NOTICE
from ai_tour_guide.app.agent.travel.contracts import TravelTurnResult
from ai_tour_guide.app.chat.models import (
    FREE_TEXT_INPUT_ID,
    ChatMessageRequest,
    ConversationTrace,
)
from ai_tour_guide.app.llm.clients import AgentLLMClient
from ai_tour_guide.app.llm.settings import LLMProvider
from ai_tour_guide.app.services.demo.questions import DEMO_WELCOME_MESSAGE
from ai_tour_guide.app.services.rag.models import RAGResult
from ai_tour_guide.app.services.rag.pipeline import answer_question_async
from ai_tour_guide.knowledge_base.retrieval.catalog import list_indexed_destinations
from ai_tour_guide.knowledge_base.search.strategies import SearchStrategy


class ConversationState(TypedDict):
    """State retained for one conversation thread."""

    messages: Annotated[list[BaseMessage], add_messages]
    flow_step: NotRequired[str]


class OuterConversationState(TypedDict):
    """Checkpointed state owned by the outer conversation graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    initialized: NotRequired[bool]
    flow_step: NotRequired[str]
    latest_request: NotRequired[dict[str, object]]
    latest_response: NotRequired[dict[str, object]]
    current_step: NotRequired[str]
    next_step: NotRequired[str]


class ConversationGraphError(RuntimeError):
    """A typed domain error raised by outer-graph validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def welcome_message_for_provider(
    provider: LLMProvider, *, knowledge_base_is_empty: bool
) -> str:
    """Return the complete conversation greeting for the selected provider."""
    if provider is LLMProvider.BAGUETTE_LLM:
        return DEMO_WELCOME_MESSAGE
    return (
        f'{WELCOME_MESSAGE}\n\n> **Knowledge base:** {EMPTY_KNOWLEDGE_BASE_NOTICE}'
        if knowledge_base_is_empty
        else WELCOME_MESSAGE
    )


def build_outer_conversation_graph(
    *,
    checkpointer: MemorySaver,
    answer_turn: Callable[[str, str, FlowStep], Awaitable[TravelTurnResult]],
    list_destination_names: Callable[[], tuple[str, ...]] | None = None,
    on_result: Callable[[TravelTurnResult], None] | None = None,
    welcome_message: str = WELCOME_MESSAGE,
):
    """Build the durable client-independent conversation graph."""

    resolve_destination_names = list_destination_names or list_indexed_destinations

    def response(
        session_id: str,
        step: FlowStep,
        message: str | None,
        *,
        request_id: UUID | None = None,
        sources: list[dict[str, object]] | None = None,
        trace: ConversationTrace | None = None,
    ) -> dict[str, object]:
        return {
            'session_id': session_id,
            'message_id': str(uuid4()),
            'step_id': step.value,
            'message': message,
            'buttons': [
                button.model_dump(mode='json')
                for button in flow_definition(step).rendered_buttons()
            ],
            'request_id': str(request_id) if request_id is not None else None,
            'sources': sources or [],
            'trace': trace.model_dump(mode='json') if trace is not None else None,
        }

    def trace_for(result: TravelTurnResult) -> ConversationTrace:
        trace = result.trace
        queries = list(trace.tool_inputs)
        return ConversationTrace(
            intent=trace.intent,
            actions=list(trace.actions),
            tool_inputs=queries,
            tool_call_count=len(queries),
            evidence_sufficient=trace.evidence_sufficient,
            retries=max(len(queries) - 1, 0),
            final_status=result.status.value,
        )

    async def initialize(state: OuterConversationState) -> dict[str, object]:
        return {
            'initialized': True,
            'flow_step': FlowStep.WELCOME.value,
            'latest_response': response(
                state['session_id'],
                FlowStep.WELCOME,
                welcome_message,
            ),
        }

    async def validate_request(state: OuterConversationState) -> dict[str, object]:
        latest_request = state.get('latest_request')
        if latest_request is None:
            raise ConversationGraphError('invalid_action', 'A request is required.')
        request = ChatMessageRequest.model_validate(latest_request)
        if not state.get('initialized'):
            raise ConversationGraphError(
                'invalid_session', 'The chat session does not exist.'
            )
        current = FlowStep(state.get('flow_step', FlowStep.WELCOME))
        if request.expected_step_id != current:
            raise ConversationGraphError(
                'stale_expected_step_id',
                'The conversation step is stale; render the latest response first.',
            )
        next_step = transition_for(current, request.input_id, text=request.text)
        if next_step is None:
            raise ConversationGraphError(
                'invalid_action', 'That input is not valid at the current step.'
            )
        return {
            'current_step': current.value,
            'next_step': next_step.value,
        }

    def request_for(state: OuterConversationState) -> ChatMessageRequest:
        latest_request = state.get('latest_request')
        if latest_request is None:
            raise ConversationGraphError('invalid_action', 'A request is required.')
        return ChatMessageRequest.model_validate(latest_request)

    def completed_response(
        state: OuterConversationState,
        message: str | None,
        *,
        request_id: UUID | None = None,
        sources: list[dict[str, object]] | None = None,
        trace: ConversationTrace | None = None,
    ) -> dict[str, object]:
        request = request_for(state)
        next_step_value = state.get('next_step')
        if next_step_value is None:
            raise ConversationGraphError('invalid_action', 'A next step is required.')
        next_step = FlowStep(next_step_value)
        return {
            'messages': [
                HumanMessage(content=request.text or request.input_id),
                AIMessage(content=message or ''),
            ],
            'flow_step': next_step.value,
            'latest_response': response(
                str(request.session_id),
                next_step,
                message,
                request_id=request_id,
                sources=sources,
                trace=trace,
            ),
        }

    async def guided_action(state: OuterConversationState) -> dict[str, object]:
        request = request_for(state)
        return completed_response(
            state,
            IDENTITY_ANSWERS[FLOW_QUESTIONS[request.input_id]],
        )

    async def catalog(state: OuterConversationState) -> dict[str, object]:
        destination_names = resolve_destination_names()
        message = (
            'Our currently covered destinations are:\n'
            + '\n'.join(f'- {name}' for name in destination_names)
            if destination_names
            else 'No destinations are currently indexed.'
        )
        return completed_response(state, message)

    async def free_text(state: OuterConversationState) -> dict[str, object]:
        request = request_for(state)
        current_step = state.get('current_step')
        if current_step is None:
            raise ConversationGraphError(
                'invalid_action', 'A current step is required.'
            )
        current = FlowStep(current_step)
        result = await answer_turn(request.text or '', str(request.session_id), current)
        if on_result is not None:
            on_result(result)
        return completed_response(
            state,
            result.answer,
            request_id=result.request_id,
            sources=[dict(source) for source in result.sources],
            trace=trace_for(result),
        )

    async def route_start(
        state: OuterConversationState,
    ) -> Literal['initialize', 'validate_request']:
        return (
            'initialize' if state.get('latest_request') is None else 'validate_request'
        )

    async def route_action(
        state: OuterConversationState,
    ) -> Literal['guided_action', 'catalog', 'free_text']:
        input_id = request_for(state).input_id
        if input_id == FREE_TEXT_INPUT_ID:
            return 'free_text'
        return 'catalog' if input_id == 'destinations' else 'guided_action'

    graph = StateGraph(OuterConversationState)
    graph.add_node('initialize', initialize)
    graph.add_node('validate_request', validate_request)
    graph.add_node('guided_action', guided_action)
    graph.add_node('catalog', catalog)
    graph.add_node('free_text', free_text)
    graph.add_conditional_edges(
        START,
        route_start,
        {'initialize': 'initialize', 'validate_request': 'validate_request'},
    )
    graph.add_edge('initialize', END)
    graph.add_conditional_edges(
        'validate_request',
        route_action,
        {
            'guided_action': 'guided_action',
            'catalog': 'catalog',
            'free_text': 'free_text',
        },
    )
    graph.add_edge('guided_action', END)
    graph.add_edge('catalog', END)
    graph.add_edge('free_text', END)
    return graph.compile(checkpointer=checkpointer)


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


__all__ = [
    'ConversationGraphError',
    'ConversationState',
    'OuterConversationState',
    'build_conversation_graph',
    'build_outer_conversation_graph',
]
