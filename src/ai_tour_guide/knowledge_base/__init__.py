"""Knowledge-base persistence, search, and LLM-context retrieval."""

from .retrieval import RetrievedContext, retrieve
from .search import (
    HybridSearchSettings,
    ScoreKind,
    SearchMetadata,
    SearchMode,
    SearchResult,
    SourceDocumentMetadata,
    search,
)

__all__ = [
    'HybridSearchSettings',
    'RetrievedContext',
    'ScoreKind',
    'SearchMetadata',
    'SearchMode',
    'SearchResult',
    'SourceDocumentMetadata',
    'retrieve',
    'search',
]
