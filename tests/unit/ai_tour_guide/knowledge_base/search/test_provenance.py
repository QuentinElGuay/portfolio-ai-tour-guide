"""Skeleton tests for source provenance extraction."""


def test_source_metadata_from_chunk_copies_document_and_chunk_provenance() -> None:
    """Call ``source_metadata_from_chunk(chunk)`` with an attached document relationship.

    Required fixture: DocumentChunkRow-like object with document metadata, section_id/path and page range.
    Expected verification: returned SourceMetadata is detached/stable and includes document identity,
    chunk identity, section identity/path and pages used by evaluation/citation validation.
    """
    pass
