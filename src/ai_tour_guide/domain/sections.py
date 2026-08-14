"""Stable identities for hierarchical document sections."""

import hashlib
import json
from collections.abc import Sequence

from ai_tour_guide.ingestion.constants import MAX_SECTION_DEPTH


def compute_section_id(
    heading_path: Sequence[tuple[int, str]],
    *,
    min_depth: int = 0,
    max_depth: int | None = None,
) -> str | None:
    """Hash the titles in an inclusive Markdown heading-depth range."""
    if min_depth < 0:
        raise ValueError('min_depth must not be negative')
    effective_max_depth = MAX_SECTION_DEPTH if max_depth is None else max_depth
    if effective_max_depth < min_depth:
        raise ValueError('max_depth must be greater than or equal to min_depth')

    titles = [
        title
        for level, title in heading_path
        if min_depth <= level <= effective_max_depth and title
    ]
    expected_depths = set(range(max(1, min_depth), effective_max_depth + 1))
    present_depths = {
        level
        for level, title in heading_path
        if min_depth <= level <= effective_max_depth and title
    }
    if present_depths != expected_depths:
        return None

    payload = json.dumps(
        titles,
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
