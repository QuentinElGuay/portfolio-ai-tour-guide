"""Formatting shared by terminal output and RAG source context."""

from ai_tour_guide.knowledge_base.models import DocumentChunkRow


def format_page_range(chunk: DocumentChunkRow) -> str:
    """Render a chunk's source-page range when it is available."""
    if chunk.page_start is None:
        return 'page unavailable'
    if chunk.page_end is None or chunk.page_end == chunk.page_start:
        return f'page {chunk.page_start}'
    return f'pages {chunk.page_start}-{chunk.page_end}'


__all__ = ['format_page_range']
