"""Shared interfaces and metadata for text embedding services.

The ingestion pipeline and retrieval agent should depend on this module rather
than on a specific inference library. This ensures that document and query
vectors use the same model configuration and normalization behavior.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


class EmbeddingError(RuntimeError):
    """Raised when an embedding model cannot produce valid vectors."""


@dataclass(frozen=True, slots=True)
class EmbeddingMetadata:
    """Effective embedding configuration and output dimensions."""

    model_name: str
    dimensions: int
    normalized: bool


@runtime_checkable
class Embedder(Protocol):
    """Minimal interface shared by ingestion and retrieval.

    Implementations must apply the same normalization policy to document and
    query vectors. ``embed_documents`` returns a two-dimensional matrix with
    one row per input text. ``embed_query`` returns one one-dimensional vector.
    """

    @property
    def metadata(self) -> EmbeddingMetadata:
        """Return the effective model configuration."""
        ...

    def embed_documents(
        self,
        texts: Sequence[str],
        *,
        batch_size: int,
    ) -> np.ndarray:
        """Return one vector per document or passage text."""
        ...

    def embed_query(self, text: str) -> np.ndarray:
        """Return one vector for a retrieval query."""
        ...
