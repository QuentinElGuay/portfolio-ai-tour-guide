"""Ranked evidence search over the knowledge-base corpus."""

from .models import (
    DEFAULT_RRF_RANK_CONSTANT,
    DEFAULT_SEARCH_MODE,
    HybridSearchSettings,
    ScoreKind,
    SearchMetadata,
    SearchMode,
    SearchResult,
)
from .service import search

__all__ = [
    'DEFAULT_RRF_RANK_CONSTANT',
    'DEFAULT_SEARCH_MODE',
    'HybridSearchSettings',
    'ScoreKind',
    'SearchMetadata',
    'SearchMode',
    'SearchResult',
    'search',
]
