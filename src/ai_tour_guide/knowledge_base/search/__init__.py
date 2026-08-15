"""Ranked evidence search over the knowledge-base corpus."""

from .models import (
    DEFAULT_RRF_RANK_CONSTANT,
    HybridSearchSettings,
    ScoreKind,
    SearchMetadata,
    SearchMode,
    SearchResult,
    SourceMetadata,
)
from .service import search

__all__ = [
    'DEFAULT_RRF_RANK_CONSTANT',
    'HybridSearchSettings',
    'ScoreKind',
    'SearchMetadata',
    'SearchMode',
    'SearchResult',
    'SourceMetadata',
    'search',
]
