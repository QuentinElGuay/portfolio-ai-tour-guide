"""Context and provider-neutral message construction for tour-guide RAG."""

import re
from collections.abc import Sequence

from ai_tour_guide.app.agent.prompts import (
    build_catalog_system_prompt,
    build_system_prompt,
)
from ai_tour_guide.app.chat.models import Message, Role
from ai_tour_guide.knowledge_base.database.models import DocumentRow
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext

CATALOG_SUBJECT_PATTERN = re.compile(
    r'\b(?:destination|destinations|region|regions|guide|guides|area|areas)\b',
    re.IGNORECASE,
)
CATALOG_REQUEST_PATTERN = re.compile(
    r'\b(?:cover|covered|available|have|offer|offered|list|catalog|catalogue|which)\b',
    re.IGNORECASE,
)


def is_destination_catalog_question(question: str) -> bool:
    """Return whether a question asks only which indexed destinations are available."""
    return bool(
        CATALOG_SUBJECT_PATTERN.search(question)
        and CATALOG_REQUEST_PATTERN.search(question)
    )


def build_catalog_messages(
    question: str, known_destination_titles: Sequence[str]
) -> tuple[Message, ...]:
    """Build messages that answer a catalog-only question without retrieval."""
    return (
        Message(
            role=Role.SYSTEM,
            content=build_catalog_system_prompt(known_destination_titles),
        ),
        Message(role=Role.USER, content=question),
    )


def build_llm_context(contexts: Sequence[RetrievedContext]) -> str:
    """Render retrieval contexts with provenance required for grounded citations."""
    return '\n\n'.join(_format_context(context) for context in contexts)


def _format_context(context: RetrievedContext) -> str:
    sources = _format_source(context.source_document, context.pages)

    return f'{sources}\nSection: {" > ".join(context.section_path)}\n\n{context.text}'


def _format_source(source_document: DocumentRow, source_pages: tuple[int, ...]) -> str:
    return (
        f'Source: {source_document.title}\n'
        f'URL: {source_document.source_url}\n'
        f'Version: {source_document.version if source_document.version is not None else "null"}\n'
        f'Pages: {", ".join(str(page) for page in source_pages)}'
    )


def build_messages(
    question: str,
    contexts: Sequence[RetrievedContext],
    *,
    known_destination_titles: Sequence[str] = (),
) -> tuple[Message, ...]:
    """Build the grounded chat messages sent to the configured backend."""
    context = build_llm_context(contexts)
    return (
        Message(
            role=Role.SYSTEM, content=build_system_prompt(known_destination_titles)
        ),
        Message(
            role=Role.USER,
            content=f'Retrieved context:\n\n{context}\n\nUser question:\n{question}',
        ),
    )


__all__ = [
    'build_catalog_messages',
    'build_llm_context',
    'build_messages',
    'build_system_prompt',
    'is_destination_catalog_question',
]
