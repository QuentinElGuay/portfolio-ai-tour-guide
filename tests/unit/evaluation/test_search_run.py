import sys
from pathlib import Path

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.search import (
    ScoreKind,
    SearchMetadata,
    SearchResult,
)

PROJECT_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.search.run import _raw_evidence


def _result(
    *,
    chunk_id: str,
    rank: int,
    section_path: list[str],
) -> SearchResult:
    document = DocumentRow(
        document_id=1,
        title='Guide to the Region of Brittany',
        source_url='https://example.test/guide.pdf',
        version=None,
    )
    chunk = DocumentChunkRow(
        document_id=document.document_id,
        chunk_id=chunk_id,
        chunk_index=rank,
        section_id='section',
        section_chunk_index=rank,
        section_path=section_path,
        text='text',
        embedding_text='text',
        character_count=4,
        document=document,
    )
    return SearchResult(
        chunk=chunk,
        search=SearchMetadata(rank, 1.0, ScoreKind.TEXT_RANK),
    )


def test_raw_evidence_preserves_duplicate_sections_and_ranking_order() -> None:
    results = [
        _result(
            chunk_id='first',
            rank=1,
            section_path=['Guide', 'Activities', 'Attractions', 'Historic sites'],
        ),
        _result(
            chunk_id='second',
            rank=2,
            section_path=['Guide', 'Activities', 'Attractions', 'Museums'],
        ),
        _result(
            chunk_id='third',
            rank=3,
            section_path=['Guide', 'Travel', 'Transport', 'Trains'],
        ),
    ]

    raw = _raw_evidence(results)
    assert len(raw) == 3
    assert raw[0] == raw[1]
    assert raw[2] != raw[0]
