"""Generate dense vector embeddings for structure-aware ingestion chunks.

The module reads the JSON array produced by ``chunking.py``, embeds each
record's ``embedding_text`` value, and writes a new JSON array ready for a
subsequent database-loading step.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import click
import numpy as np
from tqdm import tqdm


DEFAULT_MODEL_NAME = 'BAAI/bge-small-en-v1.5'
DEFAULT_BATCH_SIZE = 32


class EmbeddingError(RuntimeError):
    """Raised when chunks cannot be embedded safely."""


class EmbeddingModel(Protocol):
    """Minimal model interface used by :func:`embed_chunks`."""

    def encode(self, sentences: Sequence[str], **kwargs: Any) -> Any:
        """Return one embedding vector per input sentence."""


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Embedded chunk records plus model-level output metadata."""

    chunks: list[dict[str, Any]]
    model_name: str
    dimensions: int
    normalized: bool


def _sha256_text(text: str) -> str:
    """Return a stable SHA-256 hash for embedding input text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_chunk_records(
    chunks: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate and copy chunk records before model inference."""
    validated: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    for index, raw_chunk in enumerate(chunks):
        if not isinstance(raw_chunk, Mapping):
            raise TypeError(f'Chunk {index} must be a JSON object')

        chunk = dict(raw_chunk)
        chunk_id = chunk.get('chunk_id')
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise ValueError(f'Chunk {index} must contain a non-empty chunk_id')
        if chunk_id in seen_chunk_ids:
            raise ValueError(f'Duplicate chunk_id: {chunk_id}')
        seen_chunk_ids.add(chunk_id)

        embedding_text = chunk.get('embedding_text')
        if not isinstance(embedding_text, str) or not embedding_text.strip():
            raise ValueError(f'Chunk {chunk_id} must contain non-empty embedding_text')

        validated.append(chunk)

    return validated


def load_chunks(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a JSON array of retrieval chunks."""
    input_path = Path(path)
    with input_path.open('r', encoding='utf-8') as file:
        payload = json.load(file)

    if not isinstance(payload, list):
        raise TypeError('The chunks JSON root must be an array')

    return _validate_chunk_records(payload)


def load_embedding_model(model_name: str = DEFAULT_MODEL_NAME) -> EmbeddingModel:
    """Load a fastembed model lazily.

    Keeping the import local lets the rest of the ingestion package remain
    usable when the optional embedding dependencies are not installed.
    """
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise EmbeddingError(
            'fastembed is required for embedding. Install it with '
            '`uv add fastembed`.'
        ) from exc

    try:
        return TextEmbedding(model_name)
    except Exception as exc:  # The library wraps download and backend errors.
        raise EmbeddingError(f'Could not load embedding model {model_name!r}') from exc


def embed_chunks(
    chunks: Sequence[Mapping[str, Any]],
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    batch_size: int = DEFAULT_BATCH_SIZE,
    normalize: bool = True,
) -> EmbeddingResult:
    """Embed each chunk's embedding_text and append vector metadata."""
    if batch_size <= 0:
        raise ValueError('batch_size must be greater than zero')

    if not model_name.strip():
        raise ValueError('model_name must not be empty')

    validated_chunks = _validate_chunk_records(chunks)

    if not validated_chunks:
        return EmbeddingResult(
            chunks=[],
            model_name=model_name,
            dimensions=0,
            normalized=normalize,
        )

    embedding_model = load_embedding_model(model_name)
    all_embeddings: list[np.ndarray] = []

    try:
        for start in tqdm(
            range(0, len(validated_chunks), batch_size),
            desc='Embedding batches',
            unit='batch',
        ):
            batch = validated_chunks[start : start + batch_size]
            texts = [str(chunk['embedding_text']) for chunk in batch]

            batch_embeddings = list(
                embedding_model.embed(
                    texts,
                    batch_size=batch_size,
                )
            )

            if len(batch_embeddings) != len(batch):
                raise EmbeddingError(
                    'Embedding model returned '
                    f'{len(batch_embeddings)} vectors for {len(batch)} chunks'
                )

            all_embeddings.extend(batch_embeddings)

    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(
            f'Embedding failed for {len(validated_chunks)} chunk(s)'
        ) from exc

    embedding_matrix = np.asarray(all_embeddings, dtype=np.float32)

    if embedding_matrix.ndim != 2:
        raise EmbeddingError(
            'The embedding model returned a non-matrix result: '
            f'shape={embedding_matrix.shape}'
        )

    if embedding_matrix.shape[0] != len(validated_chunks):
        raise EmbeddingError(
            'Embedding count mismatch: '
            f'expected {len(validated_chunks)}, '
            f'got {embedding_matrix.shape[0]}'
        )

    dimensions = int(embedding_matrix.shape[1])

    embedded_chunks: list[dict[str, Any]] = []

    for chunk, vector in zip(
        validated_chunks,
        embedding_matrix,
        strict=True,
    ):
        embedded_chunk = dict(chunk)
        embedded_chunk.update(
            {
                'embedding': vector.tolist(),
                'embedding_model': model_name,
                'embedding_dimensions': dimensions,
                'embedding_normalized': normalize,
                'embedding_input_sha256': _sha256_text(
                    str(chunk['embedding_text'])
                ),
            }
        )
        embedded_chunks.append(embedded_chunk)

    return EmbeddingResult(
        chunks=embedded_chunks,
        model_name=model_name,
        dimensions=dimensions,
        normalized=normalize,
    )


def write_embedded_chunks(
    chunks: Sequence[Mapping[str, Any]],
    path: str | Path,
) -> None:
    """Atomically write embedded chunk records as a JSON array."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f'.{output_path.name}.tmp')

    try:
        with temporary_path.open('w', encoding='utf-8') as file:
            json.dump(
                list(chunks),
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
    """Embed the chunks in INPUT_PATH and write database-ready JSON."""
    try:
        chunks = load_chunks(input_path)
        result = embed_chunks(
            chunks,
            model_name=model_name,
            batch_size=batch_size,
            normalize=normalize,
        )
        write_embedded_chunks(result.chunks, output_path)
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
