"""HTTP API exposing the tour-guide RAG pipeline."""

import logging
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.app.agent.conversation import (
    ConversationGraphError,
    ConversationState,
    OuterConversationState,
    build_conversation_graph,
    build_outer_conversation_graph,
    welcome_message_for_provider,
)
from ai_tour_guide.app.agent.flow import FlowStep
from ai_tour_guide.app.agent.llm.factory import create_llm_client
from ai_tour_guide.app.agent.llm.settings import AgentsSettings
from ai_tour_guide.app.agent.rag.models import RAGErrorCategory, RAGResult
from ai_tour_guide.app.agent.rag.persistence import store_rag_result
from ai_tour_guide.app.chat.models import (
    ChatErrorCode,
    ChatFeedbackRequest,
    ChatFeedbackResponse,
    ChatMessage,
    ChatMessageRequest,
    ConversationResponse,
    LLMInfo,
    Role,
)
from ai_tour_guide.app.chat.persistence import store_chat_message, store_feedback
from ai_tour_guide.knowledge_base.database.connection import create_database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentRow

logger = logging.getLogger(__name__)


app = FastAPI(
    title='Bon Voyage Agent',
    description=(
        'AI travel companion for French destinations covered by indexed regional '
        'tourism guides.'
    ),
)
_last_health_failure: str | None = None
_conversation_checkpointer = MemorySaver()

EXTERNAL_SERVICE_ERROR_MESSAGE = (
    "_Oh là là!_ I'm having a little trouble reaching a service right now. "
    'Please try again in a short while.'
)
INTERNAL_SERVICE_ERROR_MESSAGE = (
    '_Oh là là!_ Something went a little sideways on our side. '
    'Please try again in a short while.'
)


def _chat_error_message(result: RAGResult) -> str:
    """Translate an internal error category into a safe chat message."""
    if (
        result.error is not None
        and result.error.category is RAGErrorCategory.EXTERNAL_SERVICE
    ):
        return EXTERNAL_SERVICE_ERROR_MESSAGE
    return INTERNAL_SERVICE_ERROR_MESSAGE


def _llm_info() -> LLMInfo:
    """Return the configured model identity without exposing credentials."""
    settings = AgentsSettings()
    return LLMInfo(provider=settings.llm_provider.value, model=settings.model)


def _welcome_message(*, knowledge_base_is_empty: bool) -> str:
    """Select the greeting from the active provider configuration."""
    return welcome_message_for_provider(
        AgentsSettings().llm_provider,
        knowledge_base_is_empty=knowledge_base_is_empty,
    )


def _chat_error(status_code: int, code: ChatErrorCode, message: str) -> HTTPException:
    """Create a safe typed chat error without exposing implementation details."""
    from ai_tour_guide.app.chat.models import ChatErrorResponse

    return HTTPException(
        status_code=status_code,
        detail=ChatErrorResponse(code=code, message=message).model_dump(mode='json'),
    )


async def _answer_turn(
    question: str, session_id: str, flow_step: FlowStep
) -> RAGResult:
    """Adapt the existing turn runner to the outer graph's handler contract."""
    return await _answer_question(question, session_id, flow_step=flow_step)


@app.post('/chat/start', response_model=ConversationResponse)
async def start_chat() -> ConversationResponse:
    """Create a new chat session and return its initial renderable response."""
    session_id = str(uuid4())
    graph = build_outer_conversation_graph(
        checkpointer=_conversation_checkpointer,
        answer_turn=_answer_turn,
        welcome_message=_welcome_message(
            knowledge_base_is_empty=_ensure_knowledge_base_ready()
        ),
    )
    state = await graph.ainvoke(
        {'session_id': session_id, 'messages': []},
        config={'configurable': {'thread_id': session_id}},
    )
    response = ConversationResponse.model_validate(state['latest_response']).model_copy(
        update={'llm': _llm_info()}
    )
    store_chat_message(
        ChatMessage(
            session_id=response.session_id,
            role=Role.ASSISTANT,
            content=response.message,
            flow_step=response.step_id,
            message_id=response.message_id,
            buttons=response.buttons,
        )
    )
    return response


def _ensure_knowledge_base_ready() -> bool:
    """Verify database connectivity while allowing an empty knowledge base."""
    global _last_health_failure

    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            document_id = connection.scalar(select(DocumentRow.document_id).limit(1))
    except SQLAlchemyError as exc:
        failure = 'database-unavailable'
        if _last_health_failure != failure:
            logger.warning(
                'Knowledge-base health check failed: PostgreSQL is unavailable. '
                'Check the database service and run `make db-init`.',
            )
            _last_health_failure = failure
        raise HTTPException(
            status_code=503,
            detail='The knowledge base is unavailable. Check the database service.',
        ) from exc
    finally:
        engine.dispose()

    if document_id is None:
        failure = 'empty-knowledge-base'
        if _last_health_failure != failure:
            logger.warning(
                'Knowledge-base is empty. The chat is available for guided answers, '
                'but travel questions need ingested documents. Run `make airflow`, '
                '`make ingest` or `make load-corpus` to populate it.'
            )
            _last_health_failure = failure
        return True

    _last_health_failure = None
    return False


async def _answer_question(
    question: str,
    session_id: str,
    option_id: str | None = None,
    *,
    flow_step: FlowStep = FlowStep.MAIN_MENU,
) -> RAGResult:
    """Run the session-scoped conversation graph."""
    client = create_llm_client(AgentsSettings())
    if client is None:
        raise RuntimeError('No LLM client is configured.')
    result: RAGResult | None = None

    def retain_result(value: RAGResult) -> None:
        nonlocal result
        result = value

    graph = build_conversation_graph(
        client,
        engine=None,
        strategy=None,
        checkpointer=MemorySaver(),
        on_result=retain_result,
        option_id=option_id,
    )
    conversation_input = ConversationState(
        messages=[HumanMessage(content=question)],
        flow_step=flow_step.value,
    )
    await graph.ainvoke(
        conversation_input,
        config={'configurable': {'thread_id': session_id}},
    )
    if result is None:
        raise RuntimeError('The conversation graph did not return a result.')
    return result


@app.get('/health')
async def health() -> dict[str, str]:
    """Report that the HTTP process and its knowledge base are ready."""
    _ensure_knowledge_base_ready()
    return {'status': 'ok'}


@app.post('/chat/message', response_model=ConversationResponse)
async def chat_message(request: ChatMessageRequest) -> ConversationResponse:
    """Resolve one request through the checkpointed outer conversation graph."""
    result: RAGResult | None = None

    def retain(value: RAGResult) -> None:
        nonlocal result
        result = value

    graph = build_outer_conversation_graph(
        checkpointer=_conversation_checkpointer,
        answer_turn=_answer_turn,
        on_result=retain,
        welcome_message=_welcome_message(knowledge_base_is_empty=False),
    )
    try:
        state = await graph.ainvoke(
            cast(
                OuterConversationState,
                {
                    'session_id': str(request.session_id),
                    'latest_request': request.model_dump(mode='json'),
                },
            ),
            config={'configurable': {'thread_id': str(request.session_id)}},
        )
    except ConversationGraphError as exc:
        try:
            code = ChatErrorCode(exc.code)
        except ValueError:
            code = ChatErrorCode.INVALID_ACTION
        status_code = (
            404
            if code is ChatErrorCode.INVALID_SESSION
            else 409
            if code is ChatErrorCode.STALE_STEP
            else 422
        )
        raise _chat_error(status_code, code, str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception('Unable to store RAG result')
        raise HTTPException(
            status_code=503,
            detail='Unable to store the generated answer for feedback.',
        ) from exc
    if result is not None:
        try:
            store_rag_result(result.request_id, result.to_dict())
        except SQLAlchemyError as exc:
            logger.exception('Unable to store RAG result')
            raise HTTPException(
                status_code=503,
                detail='Unable to store the generated answer for feedback.',
            ) from exc
    response_payload = dict(state['latest_response'])
    if result is not None and result.error is not None:
        response_payload['message'] = _chat_error_message(result)
        response_payload['sources'] = []
    response = ConversationResponse.model_validate(response_payload).model_copy(
        update={'llm': _llm_info()}
    )
    try:
        store_chat_message(
            ChatMessage(
                session_id=request.session_id,
                role=Role.USER,
                content=request.text or request.input_id,
                flow_step=request.expected_step_id,
                input_id=request.input_id,
            )
        )
        store_chat_message(
            ChatMessage(
                session_id=response.session_id,
                role=Role.ASSISTANT,
                content=response.message,
                flow_step=response.step_id,
                message_id=response.message_id,
                rag_request_id=response.request_id,
                sources=response.sources,
                trace=response.trace,
                buttons=response.buttons,
            )
        )
    except SQLAlchemyError as exc:
        logger.exception('Unable to store chat messages')
        raise HTTPException(
            status_code=503, detail='Unable to store chat messages.'
        ) from exc
    return response


async def _store_chat_feedback(
    request: ChatFeedbackRequest,
) -> ChatFeedbackResponse:
    """Store a rating for a previously generated chat response."""
    try:
        stored = store_feedback(request.message_id, request.helpful, request.comment)
    except SQLAlchemyError as exc:
        logger.exception('Unable to store feedback: message_id=%s', request.message_id)
        raise HTTPException(
            status_code=503,
            detail='Unable to store feedback.',
        ) from exc
    if not stored:
        raise HTTPException(status_code=404, detail='Unknown chat message ID.')
    return ChatFeedbackResponse(message_id=request.message_id)


@app.post('/chat/feedback', response_model=ChatFeedbackResponse)
async def chat_feedback(request: ChatFeedbackRequest) -> ChatFeedbackResponse:
    """Store feedback through the public chat namespace."""
    return await _store_chat_feedback(request)
