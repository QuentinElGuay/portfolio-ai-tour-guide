"""HTTP API exposing the tour-guide RAG pipeline."""

from fastapi import FastAPI
from pydantic import BaseModel, field_validator

from ai_tour_guide.agent.rag.pipeline import answer_question


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

    title: str
    page_start: int | None
    page_end: int | None


class AskResponse(BaseModel):
    """Grounded answer and the sources used to produce it."""

    answer: str
    sources: list[SourceResponse]


app = FastAPI(title='AI Tour Guide Agent')


@app.get('/health')
def health() -> dict[str, str]:
    """Report that the HTTP process is ready to receive requests."""
    return {'status': 'ok'}


@app.post('/ask', response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    """Answer a question using the configured knowledge base and LLM."""
    result = answer_question(request.question)
    sources = [
        SourceResponse(
            title=retrieved.source.title,
            page_start=retrieved.source.page_start,
            page_end=retrieved.source.page_end,
        )
        for retrieved in result.chunks
    ]
    return AskResponse(answer=result.answer, sources=sources)
