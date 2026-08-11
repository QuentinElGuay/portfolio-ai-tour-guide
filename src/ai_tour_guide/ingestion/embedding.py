"""Embed structure-aware ingestion chunks using the shared embedding package.

This module owns ingestion-specific concerns:

- validating chunk records;
- extracting each chunk's ``embedding_text``;
- showing batch progress;
- attaching vectors and provenance metadata to chunk records.

Model loading, inference, and vector normalization are delegated to the shared
``ai_tour_guide.embeddings`` package so ingestion and retrieval use the same
implementation.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from tqdm import tqdm

from ai_tour_guide.domain.chunks import Chunk, EmbeddedChunk
from ai_tour_guide.embedding import (
    DEFAULT_BATCH_SIZE,
    Embedder,
    EmbeddingError,
)


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Embedded chunk records plus the effective model configuration."""

    chunks: tuple[EmbeddedChunk, ...]
    model_name: str
    dimensions: int
    normalized: bool


def _sha256_text(text: str) -> str:
    """Return a stable SHA-256 hash for embedding input text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _validate_chunks(
    chunks: Sequence[Chunk],
) -> tuple[Chunk, ...]:
    """Validate constraints involving multiple chunks."""
    seen_chunk_ids: set[str] = set()

    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, Chunk):
            raise TypeError(f'Chunk {index} must be a Chunk instance')

        if chunk.chunk_id in seen_chunk_ids:
            raise ValueError(f'Duplicate chunk_id: {chunk.chunk_id}')

        seen_chunk_ids.add(chunk.chunk_id)

    return tuple(chunks)


def _validate_embedding_batch(
    vectors: Any,
    *,
    expected_count: int,
) -> np.ndarray:
    """Convert one embedding batch to a validated float32 matrix."""
    matrix = np.asarray(vectors, dtype=np.float32)

    if matrix.ndim != 2:
        raise EmbeddingError(
            f'The embedding model returned a non-matrix result: shape={matrix.shape}'
        )

    if matrix.shape[0] != expected_count:
        raise EmbeddingError(
            'Embedding count mismatch for batch: '
            f'expected {expected_count}, got {matrix.shape[0]}'
        )

    if matrix.shape[1] == 0:
        raise EmbeddingError('The embedding model returned empty vectors')

    if not np.isfinite(matrix).all():
        raise EmbeddingError('The embedding model returned non-finite values')

    return matrix


def embed_chunks(
    chunks: Sequence[Chunk],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    normalize: bool = True,
    embedder: Embedder,
) -> EmbeddingResult:
    """Embed each chunk's ``embedding_text`` and append vector metadata.

    ``embedder`` is supplied by the caller so query and document embedding share the
    configured model and normalization policy.
    """
    if batch_size <= 0:
        raise ValueError('batch_size must be greater than zero')

    validated_chunks: tuple[Chunk] = _validate_chunks(chunks)

    initial_metadata = embedder.metadata
    if embedder is not None and initial_metadata.normalized != normalize:
        raise ValueError(
            'Injected embedder normalization does not match normalize option: '
            f'{initial_metadata.normalized} != {normalize}'
        )

    if not validated_chunks:
        return EmbeddingResult(
            chunks=(),
            model_name=initial_metadata.model_name,
            dimensions=0,
            normalized=initial_metadata.normalized,
        )

    embedding_batches: list[np.ndarray] = []
    expected_dimensions: int | None = None

    try:
        for start in tqdm(
            range(0, len(validated_chunks), batch_size),
            desc='Embedding batches',
            unit='batch',
        ):
            batch = validated_chunks[start : start + batch_size]
            texts = [chunk.embedding_text for chunk in batch]

            matrix = _validate_embedding_batch(
                embedder.embed_documents(
                    texts,
                    batch_size=batch_size,
                ),
                expected_count=len(batch),
            )

            dimensions = int(matrix.shape[1])
            if expected_dimensions is None:
                expected_dimensions = dimensions
            elif dimensions != expected_dimensions:
                raise EmbeddingError(
                    'Embedding dimensions changed between batches: '
                    f'{expected_dimensions} != {dimensions}'
                )

            embedding_batches.append(matrix)

    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(
            f'Embedding failed for {len(validated_chunks)} chunk(s)'
        ) from exc

    embedding_matrix = np.concatenate(embedding_batches, axis=0)

    if embedding_matrix.shape[0] != len(validated_chunks):
        raise EmbeddingError(
            'Embedding count mismatch: '
            f'expected {len(validated_chunks)}, '
            f'got {embedding_matrix.shape[0]}'
        )

    dimensions = int(embedding_matrix.shape[1])
    metadata = embedder.metadata

    if metadata.dimensions not in (0, dimensions):
        raise EmbeddingError(
            'Embedder metadata dimension mismatch: '
            f'{metadata.dimensions} != {dimensions}'
        )

    embedded_chunks: list[EmbeddedChunk] = []

    for chunk, vector in zip(
        validated_chunks,
        embedding_matrix,
        strict=True,
    ):
        embedded_chunks.append(
            EmbeddedChunk(
                chunk,
                tuple(float(value) for value in vector),
                _sha256_text(chunk.embedding_text),
            )
        )

    return EmbeddingResult(
        chunks=tuple(embedded_chunks),
        model_name=metadata.model_name,
        dimensions=dimensions,
        normalized=metadata.normalized,
    )
