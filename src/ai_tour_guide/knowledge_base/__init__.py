"""Knowledge-base persistence, search, and LLM-context retrieval."""

from .retrieval import RetrievedContext, retrieve_context
from .search import (
    HybridSearchSettings,
    ScoreKind,
    SearchMetadata,
    SearchMode,
    SearchResult,
    search,
)

__all__ = [
    'HybridSearchSettings',
    'RetrievedContext',
    'ScoreKind',
    'SearchMetadata',
    'SearchMode',
    'SearchResult',
    'retrieve_context',
    'search',
]
