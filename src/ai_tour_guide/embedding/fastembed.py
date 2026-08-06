"""FastEmbed implementation of the shared text embedding interface."""

from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np

from .interfaces import Embedder, EmbeddingError, EmbeddingMetadata


class FastEmbedder(Embedder):
    """Embed passages and queries with FastEmbed and explicit normalization.

    The FastEmbed dependency is imported lazily so non-embedding commands can
    still run without the optional model runtime installed.
    """

    def __init__(
        self,
        model_name: str,
        *,
        normalize: bool = True,
        model: Any | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError('model_name must not be empty')

        self._model_name = model_name
        self._normalize_vectors = normalize
        self._dimensions = 0
        self._model = model if model is not None else self._load_model(model_name)

    @staticmethod
    def _load_model(model_name: str) -> Any:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise EmbeddingError(
                'fastembed is required for embedding. Install it with '
                '`uv add fastembed`.'
            ) from exc

        try:
            return TextEmbedding(model_name=model_name)
        except Exception as exc:
            raise EmbeddingError(
                f'Could not load embedding model {model_name!r}'
            ) from exc

    @property
    def metadata(self) -> EmbeddingMetadata:
        """Return the model name, observed vector size, and normalization mode."""
        return EmbeddingMetadata(
            model_name=self._model_name,
            dimensions=self._dimensions,
            normalized=self._normalize_vectors,
        )

    def embed_documents(
        self,
        texts: Sequence[str],
        *,
        batch_size: int,
    ) -> np.ndarray:
        """Embed document passages and return a float32 matrix."""
        if batch_size <= 0:
            raise ValueError('batch_size must be greater than zero')

        validated_texts = self._validate_texts(texts, label='document')
        if not validated_texts:
            return np.empty((0, self._dimensions), dtype=np.float32)

        try:
            # FastEmbed recommends passage_embed for stored documents. Fall
            # back to embed for compatibility with older runtimes and stubs.
            passage_embed = getattr(self._model, 'passage_embed', None)
            if callable(passage_embed):
                generated = passage_embed(
                    validated_texts,
                    batch_size=batch_size,
                )
            else:
                generated = self._model.embed(
                    validated_texts,
                    batch_size=batch_size,
                )

            matrix = self._as_matrix(
                generated,
                expected_count=len(validated_texts),
                context='document',
            )
            return self._prepare_vectors(matrix)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(
                f'Failed to embed {len(validated_texts)} document text(s)'
            ) from exc

    def embed_query(self, text: str) -> np.ndarray:
        """Embed one retrieval query using the same vector preparation path."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError('query text must be a non-empty string')

        try:
            query_embed = getattr(self._model, 'query_embed', None)
            if callable(query_embed):
                generated = query_embed(text)
            else:
                generated = self._model.embed([text], batch_size=1)

            matrix = self._as_matrix(
                generated,
                expected_count=1,
                context='query',
            )
            return self._prepare_vectors(matrix)[0]
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError('Failed to embed query text') from exc

    @staticmethod
    def _validate_texts(
        texts: Sequence[str],
        *,
        label: str,
    ) -> list[str]:
        validated: list[str] = []

        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f'{label} text {index} must be a non-empty string')
            validated.append(text)

        return validated

    @staticmethod
    def _as_matrix(
        generated: Iterable[Any],
        *,
        expected_count: int,
        context: str,
    ) -> np.ndarray:
        matrix = np.asarray(list(generated), dtype=np.float32)

        if matrix.ndim != 2:
            raise EmbeddingError(
                f'{context} embedding output must be a matrix; got shape {matrix.shape}'
            )

        if matrix.shape[0] != expected_count:
            raise EmbeddingError(
                f'{context} embedding count mismatch: expected '
                f'{expected_count}, got {matrix.shape[0]}'
            )

        if matrix.shape[1] == 0:
            raise EmbeddingError(f'{context} embedding output contains empty vectors')

        if not np.isfinite(matrix).all():
            raise EmbeddingError(
                f'{context} embedding output contains non-finite values'
            )

        return matrix

    def _prepare_vectors(self, matrix: np.ndarray) -> np.ndarray:
        """Validate dimensions and apply the configured normalization policy."""
        dimensions = int(matrix.shape[1])

        if self._dimensions not in (0, dimensions):
            raise EmbeddingError(
                'Embedding dimensions changed during runtime: '
                f'{self._dimensions} != {dimensions}'
            )

        self._dimensions = dimensions
        vectors = np.asarray(matrix, dtype=np.float32)

        if not self._normalize_vectors:
            return vectors

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise EmbeddingError('Cannot normalize a zero-length vector')

        return np.asarray(vectors / norms, dtype=np.float32)
