"""HTTP API exposing the tour-guide RAG pipeline."""

import logging
from datetime import date
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.llm.factory import create_llm_client
from ai_tour_guide.agent.llm.settings import AgentsSettings
from ai_tour_guide.agent.rag.models import RAGResult, SourceReference
from ai_tour_guide.agent.rag.persistence import (
    store_feedback,
    store_rag_result,
)
from ai_tour_guide.agent.rag.pipeline import answer_question_async
from ai_tour_guide.knowledge_base.database.connection import create_database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentRow

ASK_RESPONSE_SCHEMA_VERSION = 1
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    """Question submitted to the tour-guide agent."""

    question: str

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


app = FastAPI(title='AI Tour Guide Agent')


def _ensure_knowledge_base_ready() -> None:
    """Raise a service error when the configured schema has no corpus."""
    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            document_id = connection.scalar(select(DocumentRow.document_id).limit(1))
    except SQLAlchemyError as exc:
        logger.warning(
            'Knowledge-base health check failed: PostgreSQL is unavailable. '
            'Check the database service and run `make init-db`.',
        )
        raise HTTPException(
            status_code=503,
            detail='The knowledge base is unavailable. Check the database service.',
        ) from exc
    finally:
        engine.dispose()

    if document_id is None:
        logger.warning(
            'Knowledge-base health check failed: the public schema contains no '
            'documents. Run `make ingest` or `make load-corpus DB_SCHEMA=public`.'
        )
        raise HTTPException(
            status_code=503,
            detail=(
                'The knowledge base is empty. Run `make ingest` or '
                '`make load-corpus DB_SCHEMA=public` before starting the application.'
            ),
        )


async def _answer_question(question: str) -> RAGResult:
    """Create the configured client and run the asynchronous RAG pipeline."""
    client = create_llm_client(AgentsSettings())
    if client is None:
        raise RuntimeError('No LLM client is configured.')
    return await answer_question_async(question, llm_client=client)


@app.get('/health')
async def health() -> dict[str, str]:
    """Report that the HTTP process and its knowledge base are ready."""
    _ensure_knowledge_base_ready()
    return {'status': 'ok'}


@app.post('/ask', response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    """Answer a question using the configured knowledge base and LLM."""
    result = await _answer_question(request.question)
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
        request_id=result.request_id, answer=result.answer, sources=sources
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
