import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ai_tour_guide.embedding.fastembed import FastEmbedder


def test_fastembedder_passes_the_configured_cache_directory() -> None:
    text_embedding = MagicMock()

    with patch.dict(
        sys.modules,
        {'fastembed': SimpleNamespace(TextEmbedding=text_embedding)},
    ):
        FastEmbedder(
            'BAAI/bge-small-en-v1.5',
            cache_dir=Path('/models/fastembed'),
        )

    text_embedding.assert_called_once_with(
        model_name='BAAI/bge-small-en-v1.5',
        cache_dir='/models/fastembed',
    )


def test_fastembedder_uses_fastembed_default_cache_without_configuration() -> None:
    text_embedding = MagicMock()

    with patch.dict(
        sys.modules,
        {'fastembed': SimpleNamespace(TextEmbedding=text_embedding)},
    ):
        FastEmbedder('BAAI/bge-small-en-v1.5')

    text_embedding.assert_called_once_with(model_name='BAAI/bge-small-en-v1.5')
