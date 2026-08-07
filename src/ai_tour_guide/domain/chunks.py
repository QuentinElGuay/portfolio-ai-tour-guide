from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    document_title: str
    section_path: tuple[str, ...]
    text: str
    embedding_text: str
    page_start: int | None
    page_end: int | None
    chunk_index: int
    character_count: int

    def __post_init__(self) -> None:
        if not self.chunk_id.strip():
            raise ValueError('chunk_id must not be empty')

        if not self.text.strip():
            raise ValueError('text must not be empty')

        if not self.embedding_text.strip():
            raise ValueError('embedding_text must not be empty')

        if self.chunk_index < 0:
            raise ValueError('chunk_index must not be negative')

        if self.character_count <= 0:
            raise ValueError('character_count must be greater than zero')

        if self.page_start is not None and self.page_start < 1:
            raise ValueError('page_start must be positive')

        if self.page_end is not None and self.page_end < 1:
            raise ValueError('page_end must be positive')

        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_start > self.page_end
        ):
            raise ValueError('page_start must not exceed page_end')

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Chunk:
        return cls(
            chunk_id=str(data['chunk_id']),
            document_title=str(data['document_title']),
            section_path=tuple(data['section_path']),
            text=str(data['text']),
            embedding_text=str(data['embedding_text']),
            page_start=data.get('page_start'),
            page_end=data.get('page_end'),
            chunk_index=int(data['chunk_index']),
            character_count=int(data['character_count']),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        data = asdict(self)
        data['section_path'] = list(self.section_path)
        return data


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    """A retrieval chunk paired with its generated embedding."""

    chunk: Chunk
    embedding: tuple[float, ...]
    embedding_input_sha256: str
