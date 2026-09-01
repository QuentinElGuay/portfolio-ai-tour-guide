from dataclasses import asdict, dataclass
from datetime import date, datetime
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
    creation_date: datetime | None
    modification_date: datetime | None
    source_page_count: int
    page_count: int

    def __post_init__(self) -> None:
        """Require database-bound timestamps to include a UTC offset."""
        for field_name in ('creation_date', 'modification_date'):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not isinstance(value, datetime):
                raise TypeError(f'{field_name} must be a datetime or None')
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f'{field_name} must include timezone information')

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """Persistence-ready document produced by the ingestion pipeline."""

    metadata: DocumentMetadata
    source_checksum: str
    destination: str
    collection: str | None = None
    version: str | None = None
