"""Embed structure-aware ingestion chunks using the shared embedding package.

This module owns ingestion-specific concerns:

- validating chunk records;
- extracting each chunk's ``embedding_text``;
- showing batch progress;
- attaching vectors and provenance metadata to chunk records;
- reading and writing JSON through a Click CLI.

Model loading, inference, and vector normalization are delegated to the shared
``ai_tour_guide.embeddings`` package so ingestion and retrieval use the same
implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import numpy as np
from tqdm import tqdm

from ai_tour_guide.domain.chunks import Chunk, EmbeddedChunk
from ai_tour_guide.embedding import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MODEL_NAME,
    Embedder,
    EmbeddingError,
)
from ai_tour_guide.embedding.fastembed import FastEmbedder


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Embedded chunk records plus the effective model configuration."""

    chunks: Sequence[EmbeddedChunk]
    model_name: str
    dimensions: int
    normalized: bool


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    chunks: tuple[EmbeddedChunk, ...]
    model_name: str
    dimensions: int
    normalized: bool

    def to_records(self) -> list[dict[str, Any]]:
        """Return database-ready embedded chunk records."""
        return [
            {
                **embedded_chunk.chunk.to_dict(),
                'embedding': list(embedded_chunk.embedding),
                'embedding_model': self.model_name,
                'embedding_dimensions': self.dimensions,
                'embedding_normalized': self.normalized,
                'embedding_input_sha256': (embedded_chunk.embedding_input_sha256),
            }
            for embedded_chunk in self.chunks
        ]


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


def load_chunks(path: str | Path) -> tuple[Chunk, ...]:
    input_path = Path(path)

    with input_path.open('r', encoding='utf-8') as file:
        payload = json.load(file)

    if not isinstance(payload, list):
        raise TypeError('The chunks JSON root must be an array')

    chunks = tuple(Chunk.from_dict(item) for item in payload)

    return _validate_chunks(chunks)


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
    model_name: str = DEFAULT_MODEL_NAME,
    batch_size: int = DEFAULT_BATCH_SIZE,
    normalize: bool = True,
    embedder: Embedder,
) -> EmbeddingResult:
    """Embed each chunk's ``embedding_text`` and append vector metadata.

    ``embedder`` is injectable for unit tests. Production callers normally
    leave it as ``None``, causing this function to create a shared
    :class:`FastEmbedder` with the requested model and normalization setting.
    """
    if batch_size <= 0:
        raise ValueError('batch_size must be greater than zero')

    if not model_name.strip():
        raise ValueError('model_name must not be empty')

    validated_chunks: tuple[Chunk] = _validate_chunks(chunks)

    initial_metadata = embedder.metadata
    if embedder is not None and initial_metadata.normalized != normalize:
        raise ValueError(
            'Injected embedder normalization does not match normalize option: '
            f'{initial_metadata.normalized} != {normalize}'
        )

    if not validated_chunks:
        return EmbeddingResult(
            chunks=[],
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

    embedded_chunks: list[dict[str, Any]] = []

    for chunk, vector in zip(
        validated_chunks,
        embedding_matrix,
        strict=True,
    ):
        embedded_chunks.append(
            EmbeddedChunk(
                chunk,
                vector.tolist(),
                _sha256_text(chunk.embedding_text),
            )
        )

    return EmbeddingResult(
        chunks=embedded_chunks,
        model_name=metadata.model_name,
        dimensions=dimensions,
        normalized=metadata.normalized,
    )


def write_embedded_chunks(
    result: EmbeddingResult,
    path: str | Path,
) -> None:
    """Atomically write embedded chunk records as a JSON array."""
    records = result.to_records()

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f'.{output_path.name}.tmp')

    try:
        with temporary_path.open('w', encoding='utf-8') as file:
            json.dump(
                records,
                file,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            file.write('\n')

        temporary_path.replace(output_path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.argument(
    'input_path',
    type=click.Path(
        path_type=Path,
        exists=True,
        dir_okay=False,
        readable=True,
    ),
)
@click.option(
    '--output',
    '-o',
    'output_path',
    required=True,
    type=click.Path(path_type=Path, dir_okay=False, writable=True),
    help='Destination JSON file containing chunks and embedding vectors.',
)
@click.option(
    '--model',
    'model_name',
    default=DEFAULT_MODEL_NAME,
    show_default=True,
    help='fastembed model name or local model path.',
)
@click.option(
    '--batch-size',
    type=click.IntRange(min=1),
    default=DEFAULT_BATCH_SIZE,
    show_default=True,
    help='Number of chunks encoded per inference batch.',
)
@click.option(
    '--normalize/--no-normalize',
    default=True,
    show_default=True,
    help='L2-normalize vectors for cosine or dot-product retrieval.',
)
def main(
    input_path: Path,
    output_path: Path,
    model_name: str,
    batch_size: int,
    normalize: bool,
) -> None:
    """Embed chunks from INPUT_PATH and write them as JSON."""
    try:
        chunks = load_chunks(input_path)

        embedder = FastEmbedder(
            model_name=model_name,
            normalize=normalize,
        )

        result = embed_chunks(
            chunks,
            embedder=embedder,
            batch_size=batch_size,
        )

        write_embedded_chunks(
            result,
            output_path,
        )

    except (
        EmbeddingError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f'Embedded {len(result.chunks)} chunks')
    click.echo(f'Model: {result.model_name}')
    click.echo(f'Dimensions: {result.dimensions}')
    click.echo(f'Normalized: {result.normalized}')
    click.echo(f'Wrote: {output_path}')


if __name__ == '__main__':
    main()
