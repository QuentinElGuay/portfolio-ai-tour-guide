"""Command-line interface for querying the tour-guide knowledge base."""

import click
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_tour_guide.embedding import FastEmbedder
from ai_tour_guide.embedding.settings import EmbeddingSettings
from ai_tour_guide.knowledge_base.connection import create_database_engine
from ai_tour_guide.knowledge_base.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.search import search_text, search_vector


@click.group(context_settings={'help_option_names': ['-h', '--help']})
def main() -> None:
    """Search the tour-guide knowledge base."""


@main.command('search')
@click.argument('query')
@click.option(
    '--mode',
    type=click.Choice(['vector', 'text'], case_sensitive=False),
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
        chunks = _search(query, mode=mode, k=k)
    except (OSError, RuntimeError, SQLAlchemyError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not chunks:
        click.echo('No matching chunks found.')
        return

    for chunk in chunks:
        click.echo(_format_chunk(chunk))


def _search(query: str, *, mode: str, k: int) -> list[DocumentChunkRow]:
    """Run the selected retrieval mode and return its ranked chunks."""
    engine = create_database_engine()

    try:
        with Session(engine) as session:
            if mode == 'vector':
                settings = EmbeddingSettings()
                embedder = FastEmbedder(
                    model_name=settings.model_name,
                    normalize=settings.normalize,
                    cache_dir=settings.cache_dir,
                )
                query_embedding = embedder.embed_query(query).tolist()
                return search_vector(
                    session,
                    query_embedding,
                    k,
                    embedding_metadata=embedder.metadata,
                )

            return search_text(session, query, k)
    finally:
        engine.dispose()


def _format_chunk(chunk: DocumentChunkRow) -> str:
    """Format a chunk with the provenance needed to inspect a result."""
    page_range = _format_page_range(chunk)
    return f'{chunk.chunk_id} ({page_range})\n{chunk.text}'


def _format_page_range(chunk: DocumentChunkRow) -> str:
    """Render the source-page range when it is available."""
    if chunk.page_start is None:
        return 'page unavailable'
    if chunk.page_end is None or chunk.page_end == chunk.page_start:
        return f'page {chunk.page_start}'
    return f'pages {chunk.page_start}-{chunk.page_end}'


__all__ = ['main', 'search_command']
