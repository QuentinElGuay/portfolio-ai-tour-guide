"""Shared embedding services used by ingestion and retrieval."""

from ai_tour_guide.embedding.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_NORMALIZE,
)
from ai_tour_guide.embedding.fastembed import FastEmbedder
from ai_tour_guide.embedding.interfaces import (
    Embedder,
    EmbeddingError,
    EmbeddingMetadata,
)

__all__ = [
    'DEFAULT_BATCH_SIZE',
    'DEFAULT_NORMALIZE',
    'Embedder',
    'EmbeddingError',
    'EmbeddingMetadata',
    'FastEmbedder',
]
