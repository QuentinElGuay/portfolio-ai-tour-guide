"""Tests for immutable search-domain contracts."""

from math import inf, nan
from typing import Any

import pytest

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.search.models import (
    HybridSearchSettings,
    ScoreKind,
    SearchMetadata,
    SearchMode,
    SearchResult,
)


def _document(document_id: int = 1) -> DocumentRow:
    return DocumentRow(
        document_id=document_id,
        title=f'Document {document_id}',
        source_url=f'https://example.test/{document_id}',
    )


def _chunk(document: DocumentRow) -> DocumentChunkRow:
    return DocumentChunkRow(
        document_id=document.document_id,
        chunk_id='chunk-1',
        chunk_index=0,
        section_id='section-a',
        section_chunk_index=0,
        section_path=['Guide', 'section-a'],
        text='text',
        embedding_text='text',
        character_count=4,
        document=document,
    )


def test_search_mode_lists_vector_text_and_hybrid() -> None:
    """Verify that search mode lists vector text and hybrid."""
    assert tuple(SearchMode) == (
        SearchMode.VECTOR,
        SearchMode.TEXT,
        SearchMode.HYBRID,
    )


@pytest.mark.parametrize(
    ('kwargs', 'message'),
    [
        ({'vector_weight': -1.0}, 'vector_weight'),
        ({'vector_weight': inf}, 'vector_weight'),
        ({'vector_weight': nan}, 'vector_weight'),
        ({'text_weight': -1.0}, 'text_weight'),
        ({'text_weight': inf}, 'text_weight'),
        ({'vector_weight': 0.0, 'text_weight': 0.0}, 'at least one'),
        ({'rank_constant': -1}, 'rank_constant'),
    ],
)
def test_hybrid_settings_reject_invalid_values(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    """Verify that hybrid settings reject invalid values."""
    with pytest.raises(ValueError, match=message):
        HybridSearchSettings(**kwargs)


def test_search_result_keeps_chunk_and_search_metadata_and_exposes_document() -> None:
    """Verify that search result keeps chunk and search metadata and exposes document."""
    document = _document()
    chunk = _chunk(document)
    metadata = SearchMetadata(
        rank=3,
        score=0.72,
        score_kind=ScoreKind.COSINE_SIMILARITY,
    )

    result = SearchResult(chunk=chunk, search=metadata)

    assert result.chunk is chunk
    assert result.search is metadata
    assert result.document is document
