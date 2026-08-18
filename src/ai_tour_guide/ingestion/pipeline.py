"""Composable ingestion stages and their sequential orchestration."""

import hashlib
from collections.abc import Sequence
from pathlib import Path

import httpx

from ai_tour_guide.domain.documents import DocumentRecord
from ai_tour_guide.embedding import Embedder
from ai_tour_guide.ingestion.artifacts import (
    ChunkedDocumentArtifact,
    DownloadedPdf,
    EmbeddedDocumentArtifact,
    ParsedDocumentArtifact,
)
from ai_tour_guide.ingestion.chunking import chunk_document
from ai_tour_guide.ingestion.config import ChunkingConfig
from ai_tour_guide.ingestion.embedding import embed_chunks
from ai_tour_guide.ingestion.io import write_bytes_atomic
from ai_tour_guide.ingestion.pdf.downloader import download_pdf_bytes
from ai_tour_guide.ingestion.pdf.parser import IngestionDocument, parse_pdf_bytes
from ai_tour_guide.ingestion.pdf.serializers import (
    ParsedPdfMarkdownSerializer,
    ParsedPdfTextSerializer,
)
from ai_tour_guide.ingestion.serialization import (
    CHUNKED_DOCUMENT_JSON,
    EMBEDDED_DOCUMENT_JSON,
    PARSED_DOCUMENT_JSON,
)
from ai_tour_guide.ingestion.settings import IngestionSettings


def download_pdf_stage(
    document: IngestionDocument,
    *,
    timeout_seconds: float,
    client: httpx.Client | None = None,
) -> DownloadedPdf:
    """Download one PDF and return its content and stable checksum."""
    content = download_pdf_bytes(
        document.source_url,
        timeout_seconds=timeout_seconds,
        client=client,
    )
    return DownloadedPdf(
        document=document,
        content=content,
        source_checksum=hashlib.sha256(content).hexdigest(),
    )


def parse_pdf_stage(downloaded: DownloadedPdf) -> ParsedDocumentArtifact:
    """Parse a downloaded PDF without performing file I/O."""
    return ParsedDocumentArtifact(
        document=downloaded.document,
        source_checksum=downloaded.source_checksum,
        parsed_pdf=parse_pdf_bytes(
            downloaded.content,
            document=downloaded.document,
        ),
    )


def chunk_document_stage(
    parsed: ParsedDocumentArtifact,
    *,
    config: ChunkingConfig,
) -> ChunkedDocumentArtifact:
    """Create persistence-ready document metadata and retrieval chunks."""
    chunks = tuple(
        chunk_document(
            parsed.parsed_pdf.to_dict(),
            config=config,
        )
    )
    if not chunks:
        raise ValueError(
            f'No chunks were produced for document {parsed.document.title!r}'
        )

    return ChunkedDocumentArtifact(
        document=DocumentRecord(
            metadata=parsed.parsed_pdf.metadata,
            source_checksum=parsed.source_checksum,
            collection=parsed.document.collection,
        ),
        chunks=chunks,
        chunking=config,
    )


def embed_document_stage(
    chunked_document: ChunkedDocumentArtifact,
    *,
    embedder: Embedder,
    batch_size: int,
) -> EmbeddedDocumentArtifact:
    """Attach embeddings and their complete model metadata to every chunk."""
    initial_metadata = embedder.metadata
    embedded_chunks = embed_chunks(
        chunked_document.chunks,
        batch_size=batch_size,
        normalize=initial_metadata.normalized,
        embedder=embedder,
    )
    return EmbeddedDocumentArtifact(
        document=chunked_document.document,
        chunks=embedded_chunks.chunks,
        chunking=chunked_document.chunking,
        embedding=embedder.metadata,
    )


def load_document_stage(embedded: EmbeddedDocumentArtifact) -> int:
    """Load one complete embedded document into the knowledge base."""
    from ai_tour_guide.knowledge_base.database import insert_document_with_chunks

    return insert_document_with_chunks(
        embedded.document,
        embedded.chunks,
        embedded.chunking,
        embedded.embedding,
    )


def _write_debug_artifacts(
    artifact_directory: Path,
    downloaded: DownloadedPdf,
    parsed: ParsedDocumentArtifact,
    chunked: ChunkedDocumentArtifact,
    embedded: EmbeddedDocumentArtifact,
) -> None:
    stem = downloaded.document.filename_stem
    write_bytes_atomic(downloaded.content, artifact_directory / f'{stem}.pdf')
    ParsedPdfTextSerializer().write(
        parsed.parsed_pdf,
        artifact_directory / f'{stem}.parsed.txt',
    )
    ParsedPdfMarkdownSerializer().write(
        parsed.parsed_pdf,
        artifact_directory / f'{stem}.parsed.md',
    )
    PARSED_DOCUMENT_JSON.write(
        parsed,
        artifact_directory / f'{stem}.parsed.json',
    )
    CHUNKED_DOCUMENT_JSON.write(
        chunked,
        artifact_directory / f'{stem}.chunked.json',
    )
    EMBEDDED_DOCUMENT_JSON.write(
        embedded,
        artifact_directory / f'{stem}.embedded.json',
    )


def run_document_pipeline(
    document: IngestionDocument,
    *,
    settings: IngestionSettings,
    embedder: Embedder,
    embedding_batch_size: int,
    chunking_config: ChunkingConfig,
) -> int:
    """Execute every typed stage sequentially for one source document."""
    downloaded = download_pdf_stage(
        document,
        timeout_seconds=settings.timeout,
    )
    parsed = parse_pdf_stage(downloaded)
    chunked_document = chunk_document_stage(
        parsed,
        config=chunking_config,
    )
    embedded = embed_document_stage(
        chunked_document,
        embedder=embedder,
        batch_size=embedding_batch_size,
    )

    if settings.debug:
        _write_debug_artifacts(
            settings.tmp_folder,
            downloaded,
            parsed,
            chunked_document,
            embedded,
        )

    return load_document_stage(embedded)


def run_pipeline(
    documents: Sequence[IngestionDocument],
    *,
    settings: IngestionSettings,
    embedder: Embedder,
    embedding_batch_size: int,
    chunking_config: ChunkingConfig,
) -> tuple[int, ...]:
    """Run documents sequentially and return their database identifiers."""
    if settings.debug:
        settings.tmp_folder.mkdir(parents=True, exist_ok=True)

    return tuple(
        run_document_pipeline(
            document,
            settings=settings,
            embedder=embedder,
            embedding_batch_size=embedding_batch_size,
            chunking_config=chunking_config,
        )
        for document in documents
    )


__all__ = [
    'chunk_document_stage',
    'download_pdf_stage',
    'embed_document_stage',
    'load_document_stage',
    'parse_pdf_stage',
    'run_document_pipeline',
    'run_pipeline',
]
