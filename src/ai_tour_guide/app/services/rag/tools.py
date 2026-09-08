"""Compatibility exports for the shared tourism retrieval tool."""

from ai_tour_guide.knowledge_base.retrieval.tool import (
    DEFAULT_RETRIEVAL_QUALITY_SETTINGS,
    TOURISM_SEARCH_TOOL,
    RetrievalQualitySettings,
    RetrievalStatus,
    RetrievalToolError,
    TourismEvidence,
    TourismSearchQuery,
    TourismSearchResult,
    TourismSearchToolSpec,
    search_tourism_knowledge_base,
)

__all__ = [
    'DEFAULT_RETRIEVAL_QUALITY_SETTINGS',
    'TOURISM_SEARCH_TOOL',
    'RetrievalQualitySettings',
    'RetrievalStatus',
    'RetrievalToolError',
    'TourismEvidence',
    'TourismSearchQuery',
    'TourismSearchResult',
    'TourismSearchToolSpec',
    'search_tourism_knowledge_base',
]
