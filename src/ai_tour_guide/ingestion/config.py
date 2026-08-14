"""Immutable ingestion configuration shared across pipeline stages."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    """Effective configuration for structure-aware document chunking."""

    target_chars: int
    max_chars: int
    section_chunk_min_depth: int | None
    section_chunk_max_depth: int | None

    def __post_init__(self) -> None:
        if self.target_chars <= 0:
            raise ValueError('target_chars must be greater than zero')
        if self.max_chars <= 0:
            raise ValueError('max_chars must be greater than zero')
        if self.target_chars > self.max_chars:
            raise ValueError('target_chars must be less than or equal to max_chars')
        if (
            self.section_chunk_min_depth is not None
            and self.section_chunk_min_depth < 0
        ):
            raise ValueError('section_chunk_min_depth must not be negative')
        if (
            self.section_chunk_min_depth is not None
            and self.section_chunk_max_depth is not None
            and self.section_chunk_max_depth < self.section_chunk_min_depth
        ):
            raise ValueError(
                'section_chunk_max_depth must be greater than or equal to '
                'section_chunk_min_depth'
            )

    def to_dict(self) -> dict[str, int | None]:
        """Return a JSON-compatible representation."""
        return {
            'target_chars': self.target_chars,
            'max_chars': self.max_chars,
            'section_chunk_min_depth': self.section_chunk_min_depth,
            'section_chunk_max_depth': self.section_chunk_max_depth,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChunkingConfig:
        """Create configuration from serialized chunking metadata."""
        return cls(
            target_chars=int(data['target_chars']),
            max_chars=int(data['max_chars']),
            section_chunk_min_depth=(
                int(data['section_chunk_min_depth'])
                if data.get('section_chunk_min_depth') is not None
                else None
            ),
            section_chunk_max_depth=(
                int(data['section_chunk_max_depth'])
                if data.get('section_chunk_max_depth') is not None
                else None
            ),
        )
