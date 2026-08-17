"""Tests for document-scoped sibling-section expansion."""

from unittest.mock import MagicMock, call, patch

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow, DocumentRow
from ai_tour_guide.knowledge_base.retrieval.context import (
    build_retrieved_contexts,
    retrieve_section_chunks,
)
from ai_tour_guide.knowledge_base.search.models import (
    ScoreKind,
    SearchMetadata,
    SearchResult,
)


def _document(document_id: int) -> DocumentRow:
    return DocumentRow(
        document_id=document_id,
        title=f'Document {document_id}',
        source_url=f'https://example.test/{document_id}',
    )


def _chunk(
    document: DocumentRow,
    *,
    chunk_id: str,
    section_id: str,
    chunk_index: int,
    section_chunk_index: int,
    page: int | None = None,
) -> DocumentChunkRow:
    return DocumentChunkRow(
        document_id=document.document_id,
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        section_id=section_id,
        section_chunk_index=section_chunk_index,
        section_path=['Guide', section_id],
        text=chunk_id,
        embedding_text=chunk_id,
        page_start=page,
        page_end=page,
        character_count=len(chunk_id),
        document=document,
    )


def _result(
    chunk: DocumentChunkRow,
    *,
    rank: int,
    score: float,
    score_kind: ScoreKind = ScoreKind.TEXT_RANK,
) -> SearchResult:
    return SearchResult(
        chunk=chunk,
        search=SearchMetadata(
            rank=rank,
            score=score,
            score_kind=score_kind,
        ),
    )


def test_retrieve_section_chunks_is_document_scoped_and_ordered() -> None:
    document = _document(7)
    first = _chunk(
        document,
        chunk_id='a',
        section_id='section-a',
        chunk_index=4,
        section_chunk_index=0,
    )
    second = _chunk(
        document,
        chunk_id='b',
        section_id='section-a',
        chunk_index=8,
        section_chunk_index=1,
    )

    session = MagicMock()
    session.scalars.return_value.all.return_value = [first, second]

    siblings = retrieve_section_chunks(
        session,
        document=document,
        section_id='section-a',
    )

    assert siblings == (first, second)
    statement = session.scalars.call_args.args[0]
    sql = str(statement)
    assert 'document_chunks.document_id' in sql
    assert 'document_chunks.section_id' in sql
    assert 'document_chunks.section_chunk_index ASC' in sql
    assert 'document_chunks.chunk_index ASC' in sql


@patch('ai_tour_guide.knowledge_base.retrieval.context.retrieve_section_chunks')
def test_build_retrieved_contexts_queries_once_per_unique_document_section(
    retrieve_siblings: MagicMock,
) -> None:
    document_a = _document(1)
    document_b = _document(2)

    a1 = _chunk(
        document_a,
        chunk_id='a1',
        section_id='section-a',
        chunk_index=0,
        section_chunk_index=0,
        page=1,
    )
    a2 = _chunk(
        document_a,
        chunk_id='a2',
        section_id='section-a',
        chunk_index=1,
        section_chunk_index=1,
        page=2,
    )
    a_other = _chunk(
        document_a,
        chunk_id='a-other',
        section_id='section-b',
        chunk_index=2,
        section_chunk_index=0,
        page=3,
    )
    b1 = _chunk(
        document_b,
        chunk_id='b1',
        section_id='section-a',
        chunk_index=0,
        section_chunk_index=0,
        page=4,
    )

    # N = 4 hits, K = 3 distinct (document_id, section_id) identities.
    result_a1 = _result(a1, rank=1, score=0.91)
    result_b1 = _result(b1, rank=2, score=0.82)
    result_a2 = _result(
        a2,
        rank=3,
        score=0.73,
        score_kind=ScoreKind.COSINE_SIMILARITY,
    )
    result_a_other = _result(a_other, rank=4, score=0.64)

    def siblings_for(
        session: MagicMock,
        *,
        document: DocumentRow,
        section_id: str,
    ) -> tuple[DocumentChunkRow, ...]:
        del session
        identity = (document.document_id, section_id)
        if identity == (1, 'section-a'):
            return (a1, a2)
        if identity == (2, 'section-a'):
            return (b1,)
        if identity == (1, 'section-b'):
            return (a_other,)
        raise AssertionError(f'unexpected sibling query: {identity}')

    retrieve_siblings.side_effect = siblings_for
    session = MagicMock()

    contexts = build_retrieved_contexts(
        session,
        [result_a1, result_b1, result_a2, result_a_other],
    )

    # Deduplication happens before sibling expansion: exactly K queries.
    assert retrieve_siblings.call_count == 3
    assert retrieve_siblings.call_args_list == [
        call(session, document=document_a, section_id='section-a'),
        call(session, document=document_b, section_id='section-a'),
        call(session, document=document_a, section_id='section-b'),
    ]

    # Exactly one context exists per unique document+section identity.
    identities = [
        (context.document.document_id, context.section_id)
        for context in contexts
    ]
    assert identities == [
        (1, 'section-a'),
        (2, 'section-a'),
        (1, 'section-b'),
    ]
    assert len(identities) == len(set(identities))

    # All original hits for the duplicate group survive unchanged and in rank order.
    first_context = contexts[0]
    assert first_context.search_results == (result_a1, result_a2)
    assert first_context.search_results[0] is result_a1
    assert first_context.search_results[1] is result_a2
    assert first_context.search_results[0].search.rank == 1
    assert first_context.search_results[0].search.score == 0.91
    assert first_context.search_results[1].search.rank == 3
    assert first_context.search_results[1].search.score == 0.73
    assert first_context.search_results[1].search.score_kind is ScoreKind.COSINE_SIMILARITY

    # Expanded content comes from all ordered siblings, not only matched chunks.
    assert first_context.chunks == (a1, a2)
    assert first_context.text == 'a1\n\na2'
    assert first_context.pages == (1, 2)


@patch('ai_tour_guide.knowledge_base.retrieval.context.retrieve_section_chunks')
def test_build_retrieved_contexts_empty_results_issue_no_sibling_queries(
    retrieve_siblings: MagicMock,
) -> None:
    contexts = build_retrieved_contexts(MagicMock(), [])
    assert contexts == []
    retrieve_siblings.assert_not_called()
