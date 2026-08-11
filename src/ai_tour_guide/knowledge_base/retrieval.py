"""Reusable retrieval orchestration for the knowledge base."""

from typing import Literal

from sqlalchemy.orm import Session

from ai_tour_guide.embedding import FastEmbedder
from ai_tour_guide.embedding.settings import EmbeddingSettings
from ai_tour_guide.knowledge_base.connection import create_database_engine
from ai_tour_guide.knowledge_base.models import DocumentChunkRow
from ai_tour_guide.knowledge_base.search import search_text, search_vector

SearchMode = Literal['vector', 'text']


def retrieve(
    query: str,
    *,
    mode: SearchMode = 'vector',
    k: int = 5,
) -> list[DocumentChunkRow]:
    """Retrieve ranked document chunks using the selected search mode.

    This function owns the database, session, and embedding lifecycle so
    callers only need to choose a query, search mode, and result count.
    """
    if mode not in ('vector', 'text'):
        raise ValueError(f'Unsupported search mode: {mode!r}')

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


__all__ = ['SearchMode', 'retrieve']
