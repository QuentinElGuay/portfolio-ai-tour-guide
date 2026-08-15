"""Reusable conversion from attached ORM chunks to stable source provenance."""

from ai_tour_guide.knowledge_base.database.models import DocumentChunkRow

from .models import SourceDocumentMetadata


def source_metadata_from_chunk(chunk: DocumentChunkRow) -> SourceDocumentMetadata:
    """Copy provenance from an ORM chunk while its document relationship is available."""
    document = chunk.document
    return SourceDocumentMetadata(
        document_id=chunk.document_id,
        chunk_id=chunk.chunk_id,
        title=document.title,
        url=document.source_url,
        publisher=document.publisher,
        publication_date=document.publication_date,
        collection=document.collection,
        version=document.version,
        section_id=chunk.section_id,
        section_path=tuple(chunk.section_path),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
    )


__all__ = ['source_metadata_from_chunk']
