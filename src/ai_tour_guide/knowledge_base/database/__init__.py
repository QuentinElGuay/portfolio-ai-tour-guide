"""PostgreSQL persistence layer for the knowledge base."""

from .connection import create_database_engine
from .insert import insert_document_with_chunks
from .models import DocumentChunkRow, DocumentRow, EmbeddingModelRow
from .settings import DatabaseSettings

__all__ = [
    'DatabaseSettings',
    'DocumentChunkRow',
    'DocumentRow',
    'EmbeddingModelRow',
    'create_database_engine',
    'insert_document_with_chunks',
]
