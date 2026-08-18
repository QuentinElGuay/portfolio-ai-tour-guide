"""Formatting shared by terminal output and RAG source context."""

from collections.abc import Sequence


def format_page_range(page_start: int | None, page_end: int | None) -> str:
    """Render a chunk's source-page range when it is available."""
    if page_start is None:
        return 'page unavailable'
    if page_end is None or page_end == page_start:
        return f'page {page_start}'
    return f'pages {page_start}-{page_end}'


def format_pages(pages: Sequence[int]) -> str:
    """Render sorted page numbers in natural language."""
    numbers = [str(page) for page in pages]
    if len(numbers) == 1:
        return f'page {numbers[0]}'
    if len(numbers) == 2:
        return f'pages {numbers[0]} and {numbers[1]}'
    return f'pages {", ".join(numbers[:-1])} and {numbers[-1]}'


__all__ = ['format_page_range', 'format_pages']
