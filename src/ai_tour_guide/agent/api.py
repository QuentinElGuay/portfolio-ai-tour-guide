"""HTTP API exposing the tour-guide RAG pipeline."""

from datetime import date
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.rag.models import RAGResult, SourceReference
from ai_tour_guide.agent.rag.pipeline import answer_question
from ai_tour_guide.knowledge_base.database.connection import create_database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentRow

ASK_RESPONSE_SCHEMA_VERSION = 1


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


app = FastAPI(title='AI Tour Guide Agent')


def _ensure_knowledge_base_ready() -> None:
    """Raise a service error when the configured schema has no corpus."""
    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            document_id = connection.scalar(select(DocumentRow.document_id).limit(1))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail='The knowledge base is unavailable. Check the database service.',
        ) from exc
    finally:
        engine.dispose()

    if document_id is None:
        raise HTTPException(
            status_code=503,
            detail=(
                'The knowledge base is empty. Run `make load-corpus DB_SCHEMA=public` '
                'before starting the application.'
            ),
        )


@app.get('/health')
def health() -> dict[str, str]:
    """Report that the HTTP process and its knowledge base are ready."""
    _ensure_knowledge_base_ready()
    return {'status': 'ok'}


@app.post('/ask', response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    """Answer a question using the configured knowledge base and LLM."""
    result: RAGResult = answer_question(request.question)
    sources = [SourceResponse.from_reference(source) for source in result.sources]
    return AskResponse(
        request_id=result.request_id, answer=result.answer, sources=sources
    )
