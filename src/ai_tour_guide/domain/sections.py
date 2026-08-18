"""Stable identities for hierarchical document sections."""

import re
import unicodedata
from collections.abc import Sequence

from ai_tour_guide.ingestion.constants import MAX_SECTION_DEPTH

_NON_ALPHANUMERIC_RE = re.compile(r'[^a-z0-9]+')


def compute_section_id(
    heading_path: Sequence[tuple[int, str]],
    *,
    min_depth: int = 0,
    max_depth: int | None = None,
) -> str:
    """Return a readable slug for titles in a heading-depth range."""
    if min_depth < 0:
        raise ValueError('min_depth must not be negative')
    effective_max_depth = MAX_SECTION_DEPTH if max_depth is None else max_depth
    if effective_max_depth < min_depth:
        raise ValueError('max_depth must be greater than or equal to min_depth')

    titles = (
        title
        for level, title in heading_path
        if min_depth <= level <= effective_max_depth and title
    )
    slugs = (_slugify(title) for title in titles)
    slug = '-'.join(item for item in slugs if item)
    return slug or 'root'


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value)
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    return _NON_ALPHANUMERIC_RE.sub('-', ascii_value).strip('-')


def slugify_section_path(section_path: Sequence[str]) -> tuple[str, ...]:
    """Return the stable slugs for a section path."""
    return tuple(_slugify(title) for title in section_path)
