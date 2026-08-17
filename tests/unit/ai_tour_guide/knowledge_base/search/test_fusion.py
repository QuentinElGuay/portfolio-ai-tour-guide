"""Tests for reciprocal-rank fusion."""

import pytest

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.search.fusion import reciprocal_rank_fusion
from ai_tour_guide.knowledge_base.search.models import (
    ScoreKind,
    SearchMetadata,
    SearchResult,
)


def _result(
    *,
    document_id: int,
    chunk_id: str,
    rank: int,
    score: float,
) -> SearchResult:
    document = DocumentRow(
        document_id=document_id,
        title=f'Document {document_id}',
        source_url=f'https://example.test/{document_id}',
    )
    chunk = DocumentChunkRow(
        document_id=document_id,
        chunk_id=chunk_id,
        chunk_index=rank,
        section_id='section-a',
        section_chunk_index=rank,
        section_path=['Guide', 'section-a'],
        text=chunk_id,
        embedding_text=chunk_id,
        character_count=len(chunk_id),
        document=document,
    )
    return SearchResult(
        chunk=chunk,
        search=SearchMetadata(
            rank=rank,
            score=score,
            score_kind=ScoreKind.TEXT_RANK,
        ),
    )


def test_reciprocal_rank_fusion_deduplicates_shared_chunks() -> None:
    shared_vector = _result(
        document_id=1,
        chunk_id='shared',
        rank=1,
        score=0.9,
    )
    vector_only = _result(
        document_id=1,
        chunk_id='vector-only',
        rank=2,
        score=0.8,
    )
    shared_text = _result(
        document_id=1,
        chunk_id='shared',
        rank=1,
        score=0.7,
    )

    fused = reciprocal_rank_fusion(
        [
            ([shared_vector, vector_only], 1.0),
            ([shared_text], 1.0),
        ],
        k=5,
        rank_constant=60,
    )

    assert len(fused) == 2
    assert fused[0].chunk.chunk_id == 'shared'
    assert fused[0].search.score == pytest.approx(2 / 61)
    assert fused[0].search.score_kind is ScoreKind.RRF


def test_reciprocal_rank_fusion_keeps_chunk_and_replaces_search_metadata() -> None:
    original = _result(
        document_id=1,
        chunk_id='chunk-1',
        rank=7,
        score=0.42,
    )

    [fused] = reciprocal_rank_fusion(
        [([original], 2.0)],
        k=1,
        rank_constant=10,
    )

    assert fused.chunk is original.chunk
    assert fused.search.rank == 1
    assert fused.search.score == pytest.approx(2 / 11)
    assert fused.search.score_kind is ScoreKind.RRF
