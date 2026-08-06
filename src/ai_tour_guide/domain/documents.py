from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Descriptive metadata resolved from a source document."""

    title: str | None
    source_url: str
    publisher: str | None
    publication_date: date | None
    authors: tuple[str, ...]
    subject: str | None
    keywords: tuple[str, ...]
    creator: str | None
    producer: str | None
    format: str | None
    creation_date: str | None
    modification_date: str | None
    source_page_count: int
    page_count: int


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """Persistence-ready document produced by the ingestion pipeline."""

    metadata: DocumentMetadata
    collection: str | None = None  # TODO
    version: str | None = None  # TODO
    source_checksum: str
