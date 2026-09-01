"""HTTP API exposing the tour-guide RAG pipeline."""

import logging
from datetime import date
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.conversation import (
    ConversationState,
    build_conversation_graph,
)
from ai_tour_guide.agent.llm.factory import create_llm_client
from ai_tour_guide.agent.llm.settings import AgentsSettings
from ai_tour_guide.agent.rag.models import Emotion, RAGResult, SourceReference
from ai_tour_guide.agent.rag.persistence import (
    store_feedback,
    store_rag_result,
)
from ai_tour_guide.knowledge_base.database.connection import create_database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentRow

ASK_RESPONSE_SCHEMA_VERSION = 1
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    """Question submitted to the tour-guide agent."""

    question: str
    option_id: str | None = None
    session_id: str = Field(default_factory=lambda: str(uuid4()))

    @field_validator('question')
    @classmethod
    def validate_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError('question must not be empty')
        return question


class SourceResponse(BaseModel):
    """Source reference displayed alongside an answer."""

    source_url: str
    version: str | None
    title: str
    publisher: str | None
    collection: str | None
    publication_date: date | None
    pages: list[int]

    @classmethod
    def from_reference(cls, reference: SourceReference) -> SourceResponse:
        """Build an API response from an internal source reference."""
        return cls(
            source_url=reference.source_url,
            version=reference.version,
            title=reference.title,
            publisher=reference.publisher,
            collection=reference.collection,
            publication_date=reference.publication_date,
            pages=list(reference.pages),
        )


class AskResponse(BaseModel):
    """Grounded answer and the sources used to produce it."""

    schema_version: int = ASK_RESPONSE_SCHEMA_VERSION
    request_id: UUID
    answer: str
    sources: list[SourceResponse]
    emotion: Emotion = Emotion.NEUTRAL
    next_option_ids: list[str] = []


class FeedbackRequest(BaseModel):
    """Anonymous rating for a generated RAG answer."""

    request_id: UUID
    helpful: bool
    comment: str | None = None

    @field_validator('comment')
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class FeedbackResponse(BaseModel):
    """Confirmation that feedback was associated with a RAG result."""

    request_id: UUID


app = FastAPI(title='Baguette Voyages Agent')
_last_health_failure: str | None = None
_conversation_checkpointer = MemorySaver()


def _ensure_knowledge_base_ready() -> None:
    """Raise a service error when the configured schema has no corpus."""
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
                'Knowledge-base health check failed: the public schema contains no '
                'documents. Run `make airflow`, `make ingest` or `make load-corpus` '
                'to ingest documents in the knowledge-base.'
            )
            _last_health_failure = failure
        raise HTTPException(
            status_code=503,
            detail=(
                'Knowledge-base health check failed: the public schema contains no '
                'documents. Run `make airflow`, `make ingest` or `make load-corpus` '
                'to ingest documents in the knowledge-base.'
            ),
        )

    _last_health_failure = None


async def _answer_question(
    question: str, session_id: str, option_id: str | None = None
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
        checkpointer=_conversation_checkpointer,
        on_result=retain_result,
        option_id=option_id,
    )
    conversation_input = ConversationState(
        messages=[HumanMessage(content=question)],
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


@app.post('/ask', response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    """Answer a question using the configured knowledge base and LLM."""
    result = await _answer_question(
        request.question, request.session_id, request.option_id
    )
    try:
        store_rag_result(result.request_id, result.to_dict())
    except SQLAlchemyError as exc:
        logger.exception('Unable to store RAG result: request_id=%s', result.request_id)
        raise HTTPException(
            status_code=503,
            detail='Unable to store the generated answer for feedback.',
        ) from exc
    sources = [SourceResponse.from_reference(source) for source in result.sources]
    return AskResponse(
        request_id=result.request_id,
        answer=result.answer,
        sources=sources,
        emotion=result.generated.emotion,
        next_option_ids=list(result.retrieval_metadata.get('next_option_ids', ())),
    )


@app.post('/feedback', response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Store a rating for a previously generated RAG answer."""
    try:
        stored = store_feedback(request.request_id, request.helpful, request.comment)
    except SQLAlchemyError as exc:
        logger.exception('Unable to store feedback: request_id=%s', request.request_id)
        raise HTTPException(
            status_code=503,
            detail='Unable to store feedback.',
        ) from exc
    if not stored:
        raise HTTPException(status_code=404, detail='Unknown RAG result request ID.')
    return FeedbackResponse(request_id=request.request_id)
