"""Skeleton tests for sibling-section expansion."""


def test_retrieve_section_chunks_is_document_scoped_and_ordered() -> None:
    """Call ``retrieve_section_chunks(session, document_id=..., section_id=...)``.

    Required mocks: Session.scalars result containing sibling DocumentChunkRows.
    Expected verification: query constrains both document and section, eager-loads document provenance and
    orders by section_chunk_index then chunk_index.
    """
    


def test_build_retrieved_contexts_deduplicates_sections_without_losing_search_hits() -> None:
    """Call ``build_retrieved_contexts(session, results)`` with two hits from one section and another section.

    Required fixtures/mocks: ranked SearchResults, patched ``retrieve_section_chunks`` returning siblings,
    and provenance conversion for each sibling.
    Expected verification: one context per document+section in first-hit order, sibling text joined once,
    all triggering SearchResults retained, and sources cover every sibling supplied to the LLM.
    """
    
