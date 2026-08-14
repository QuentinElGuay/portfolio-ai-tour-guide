"""Command-line interface for querying the tour-guide knowledge base."""

import click
from sqlalchemy.exc import SQLAlchemyError

from ai_tour_guide.agent.api import ASK_RESPONSE_SCHEMA_VERSION
from ai_tour_guide.agent.rag.pipeline import answer_question
from ai_tour_guide.agent.source_formatting import format_page_range
from ai_tour_guide.knowledge_base.retrieval import (
    RetrievedChunk,
    SearchMode,
    retrieve,
)


@click.group(context_settings={'help_option_names': ['-h', '--help']})
def main() -> None:
    """Search the tour-guide knowledge base."""


@main.command('search')
@click.argument('query')
@click.option(
    '--mode',
    type=click.Choice([mode.value for mode in SearchMode], case_sensitive=False),
    default='vector',
    show_default=True,
    help='Use semantic vector search or PostgreSQL full-text search.',
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
        chunks = retrieve(query, mode=mode, k=k)
    except (OSError, RuntimeError, SQLAlchemyError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not chunks:
        click.echo('No matching chunks found.')
        return

    for chunk in chunks:
        click.echo(_format_chunk(chunk))


@main.command('ask')
@click.argument('question')
@click.option(
    '--mode',
    type=click.Choice([mode.value for mode in SearchMode], case_sensitive=False),
    default='vector',
    show_default=True,
    help='Use semantic vector search or PostgreSQL full-text search.',
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
        result = answer_question(question, mode=mode, k=k)
    except (OSError, RuntimeError, SQLAlchemyError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if verbose:
        click.echo(json.dumps(result.to_dict(), indent=2))
        return

    click.echo(
        json.dumps(
            {
                'schema_version': ASK_RESPONSE_SCHEMA_VERSION,
                'answer': result.answer,
                'sources': [source.to_dict() for source in result.sources],  #TODO: see contexts
            }
        )
    )


def _format_chunk(result: RetrievedChunk) -> str:
    """Format a chunk with the provenance needed to inspect a result."""
    chunk = result.chunk
    return (
        f'{chunk.chunk_id} ({format_page_range(chunk)}) '
        f'[rank {result.rank}, score {result.score:.4f} '
        f'{result.score_kind.value}]\n{result.text}'
    )


__all__ = ['ask_command', 'main', 'search_command']
