"""Shared embedding services used by ingestion and retrieval."""

from .fastembed import DEFAULT_BATCH_SIZE, DEFAULT_MODEL_NAME, FastEmbedder
from .interfaces import Embedder, EmbeddingError, EmbeddingMetadata

__all__ = [
    'DEFAULT_BATCH_SIZE',
    'DEFAULT_MODEL_NAME',
    'Embedder',
    'EmbeddingError',
    'EmbeddingMetadata',
    'FastEmbedder',
]
