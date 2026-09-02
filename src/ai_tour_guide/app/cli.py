"""Command-line interface for querying the tour-guide knowledge base."""

import asyncio
from uuid import UUID

import click
import questionary
from questionary import Choice
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.app.agent.rag.models import RAG_RESULT_SCHEMA_VERSION
from ai_tour_guide.app.agent.rag.persistence import store_rag_result
from ai_tour_guide.app.agent.rag.pipeline import answer_question
from ai_tour_guide.app.agent.source_formatting import format_page_range
from ai_tour_guide.app.chat.backends import create_backend
from ai_tour_guide.app.chat.models import FREE_TEXT_INPUT_ID
from ai_tour_guide.app.chat.persistence import store_feedback
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
                'schema_version': RAG_RESULT_SCHEMA_VERSION,
                'request_id': str(result.request_id),
                'answer': result.answer,
                'sources': [source.to_dict() for source in result.sources],
                'emotion': result.generated.emotion.value,
            }
        )
    )


@main.command('feedback')
@click.argument('message_id')
@click.option(
    '--helpful/--not-helpful',
    required=True,
    help='Whether the generated answer was helpful.',
)
@click.option('--comment', default=None, help='Optional feedback comment.')
def feedback_command(message_id: str, helpful: bool, comment: str | None) -> None:
    """Submit feedback for a previously generated chat message."""
    try:
        parsed_message_id = UUID(message_id)
        stored = store_feedback(parsed_message_id, helpful, comment)
    except (SQLAlchemyError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not stored:
        raise click.ClickException('Unknown chat message ID.')
    click.echo(f'Feedback stored for message {parsed_message_id}.')


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
    """Start an interactive backend-owned conversation."""
    del mode, k
    backend = create_backend()
    response = asyncio.run(backend.start_chat())
    click.echo(response.message)

    while True:
        choices = [
            Choice(button.label, value=button.input_id) for button in response.buttons
        ]
        choices.extend(
            [
                Choice('Write a message', value=FREE_TEXT_INPUT_ID),
                Choice('/new', value='/new'),
                Choice('/quit', value='/quit'),
            ]
        )
        selection = questionary.select('Choose an action', choices=choices).ask()
        if selection in (None, '/quit'):
            click.echo('Chat ended.')
            return
        if selection == '/new':
            response = asyncio.run(backend.start_chat())
            click.echo(response.message)
            continue

        text = None
        if selection == FREE_TEXT_INPUT_ID:
            text = questionary.text('Write a message').ask()
            if text is None or text.strip() == '/quit':
                click.echo('Chat ended.')
                return
            if text.strip() == '/new':
                response = asyncio.run(backend.start_chat())
                click.echo(response.message)
                continue
        try:
            response = asyncio.run(
                backend.send_message(
                    str(response.session_id),
                    str(response.step_id),
                    selection,
                    text,
                )
            )
        except (OSError, RuntimeError, SQLAlchemyError, TypeError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(response.message)


def _format_search_result(result: SearchResult) -> str:
    """Format a search result with the provenance needed to inspect a it."""
    return (
        f'{result.chunk.chunk_id} ({format_page_range(result.page_start, result.page_end)}) '
        f'[rank {result.search.rank}, score {result.search.score:.4f} '
        f'{result.search.score_kind.value}]\n{result.chunk.text}'
    )


__all__ = ['ask_command', 'chat_command', 'feedback_command', 'main', 'search_command']
