"""Command-line interface for querying the tour-guide knowledge base."""

from uuid import UUID

import click
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.api import ASK_RESPONSE_SCHEMA_VERSION
from ai_tour_guide.agent.rag.persistence import (
    store_feedback,
    store_rag_result,
)
from ai_tour_guide.agent.rag.pipeline import answer_question
from ai_tour_guide.agent.source_formatting import format_page_range
from ai_tour_guide.knowledge_base.retrieval import retrieve_context
from ai_tour_guide.knowledge_base.search import (
    DEFAULT_SEARCH_MODE,
    SearchMode,
    SearchResult,
)


@click.group(context_settings={'help_option_names': ['-h', '--help']})
def main() -> None:
    """Search the tour-guide knowledge base."""


@main.command('search')
@click.argument('query')
@click.option(
    '--mode',
    type=click.Choice([mode.value for mode in SearchMode], case_sensitive=False),
    default=DEFAULT_SEARCH_MODE.value,
    show_default=True,
    help='Use vector, PostgreSQL full-text, or hybrid search.',
)
@click.option(
    '--k',
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help='Maximum number of chunks to return.',
)
def search_command(query: str, mode: str, k: int) -> None:
    """Search for document chunks matching QUERY."""
    try:
        contexts = retrieve_context(query, search_mode=SearchMode(mode), k=k)
    except (OSError, RuntimeError, SQLAlchemyError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not contexts:
        click.echo('No matching chunks found.')
        return

    for context in contexts:
        for result in context.search_results:
            click.echo(_format_search_result(result))


@main.command('ask')
@click.argument('question')
@click.option(
    '--mode',
    type=click.Choice([mode.value for mode in SearchMode], case_sensitive=False),
    default=DEFAULT_SEARCH_MODE.value,
    show_default=True,
    help='Use vector, PostgreSQL full-text, or hybrid search.',
)
@click.option(
    '--k',
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help='Maximum number of chunks to use as context.',
)
@click.option(
    '--verbose', is_flag=True, help='Print the complete serialized RAG result.'
)
def ask_command(question: str, mode: str, k: int, verbose: bool) -> None:
    """Answer QUESTION using the tour-guide knowledge base."""
    import json

    try:
        result = answer_question(question, mode=SearchMode(mode), k=k)
        store_rag_result(result.request_id, result.to_dict())
    except (OSError, RuntimeError, SQLAlchemyError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if verbose:
        click.echo(json.dumps(result.to_dict(), indent=2))
        return

    click.echo(
        json.dumps(
            {
                'schema_version': ASK_RESPONSE_SCHEMA_VERSION,
                'request_id': str(result.request_id),
                'answer': result.answer,
                'sources': [source.to_dict() for source in result.sources],
            }
        )
    )


@main.command('feedback')
@click.argument('request_id')
@click.option(
    '--helpful/--not-helpful',
    required=True,
    help='Whether the generated answer was helpful.',
)
@click.option('--comment', default=None, help='Optional feedback comment.')
def feedback_command(request_id: str, helpful: bool, comment: str | None) -> None:
    """Submit feedback for a previously generated RAG answer."""
    try:
        parsed_request_id = UUID(request_id)
        stored = store_feedback(parsed_request_id, helpful, comment)
    except (SQLAlchemyError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not stored:
        raise click.ClickException('Unknown RAG result request ID.')
    click.echo(f'Feedback stored for request {parsed_request_id}.')


@main.command('chat')
@click.option(
    '--mode',
    type=click.Choice([mode.value for mode in SearchMode], case_sensitive=False),
    default=DEFAULT_SEARCH_MODE.value,
    show_default=True,
    help='Use vector, PostgreSQL full-text, or hybrid search.',
)
@click.option(
    '--k',
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help='Maximum number of chunks to use as context.',
)
def chat_command(mode: str, k: int) -> None:
    """Start an interactive question-and-feedback chat."""
    click.echo('Chat started. Type /exit to leave.')

    while True:
        question = click.prompt('You').strip()
        if question.lower() == '/exit':
            click.echo('Chat ended.')
            return
        if not question:
            click.echo('Please enter a question or /exit.')
            continue

        try:
            result = answer_question(question, mode=SearchMode(mode), k=k)
            store_rag_result(result.request_id, result.to_dict())
        except (OSError, RuntimeError, SQLAlchemyError, TypeError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(f'Guide: {result.answer}')
        click.echo(f'Request ID: {result.request_id}')
        rating = click.prompt(
            'Was this answer helpful?',
            type=click.Choice(['positive', 'negative', 'skip'], case_sensitive=False),
            default='skip',
            show_default=True,
        )
        if rating.lower() == 'skip':
            continue

        try:
            store_feedback(result.request_id, rating.lower() == 'positive')
        except (SQLAlchemyError, TypeError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo('Feedback stored.')


def _format_search_result(result: SearchResult) -> str:
    """Format a search result with the provenance needed to inspect a it."""
    return (
        f'{result.chunk.chunk_id} ({format_page_range(result.page_start, result.page_end)}) '
        f'[rank {result.search.rank}, score {result.search.score:.4f} '
        f'{result.search.score_kind.value}]\n{result.chunk.text}'
    )


__all__ = ['ask_command', 'chat_command', 'feedback_command', 'main', 'search_command']
