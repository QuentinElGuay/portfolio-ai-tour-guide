from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Descriptive metadata resolved from a source document."""

    title: str
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

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """Persistence-ready document produced by the ingestion pipeline."""

    metadata: DocumentMetadata
    source_checksum: str
    collection: str | None = None  # TODO
    version: str | None = None  # TODO
