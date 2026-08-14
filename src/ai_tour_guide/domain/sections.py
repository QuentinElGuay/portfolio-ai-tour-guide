"""Stable identities for hierarchical document sections."""

import hashlib
import json
from collections.abc import Sequence


def compute_section_id(
    heading_path: Sequence[tuple[int, str]],
    *,
    min_depth: int,
    max_depth: int,
) -> str | None:
    """Hash the titles in an inclusive Markdown heading-depth range."""
    if min_depth <= 0:
        raise ValueError('min_depth must be greater than zero')
    if max_depth < min_depth:
        raise ValueError('max_depth must be greater than or equal to min_depth')

    titles = [
        title
        for level, title in heading_path
        if min_depth <= level <= max_depth and title
    ]
    expected_depths = set(range(min_depth, max_depth + 1))
    present_depths = {
        level
        for level, title in heading_path
        if min_depth <= level <= max_depth and title
    }
    if present_depths != expected_depths:
        return None

    payload = json.dumps(
        titles,
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
