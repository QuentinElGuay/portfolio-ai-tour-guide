"""JSON artifact serializers used at ingestion pipeline boundaries."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from ai_tour_guide.ingestion.artifacts import (
    ChunkedDocumentArtifact,
    EmbeddedDocumentArtifact,
    ParsedDocumentArtifact,
)
from ai_tour_guide.ingestion.io import write_text_atomic


class JsonArtifact(Protocol):
    """Structural type implemented by every serializable stage artifact."""

    def to_dict(self) -> dict[str, Any]: ...


class ArtifactJsonSerializer[T: JsonArtifact]:
    """Read and atomically write one versioned JSON artifact type."""

    def __init__(
        self,
        artifact_from_dict: Callable[[dict[str, Any]], T],
    ) -> None:
        self._artifact_from_dict = artifact_from_dict

    def serialize(self, artifact: T) -> str:
        return (
            json.dumps(
                artifact.to_dict(),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + '\n'
        )

    def deserialize(self, content: str) -> T:
        data = json.loads(content)
        if not isinstance(data, dict):
            raise TypeError('Artifact JSON root must be an object')
        return self._artifact_from_dict(data)

    def write(self, artifact: T, path: str | Path) -> Path:
        return write_text_atomic(self.serialize(artifact), path)

    def read(self, path: str | Path) -> T:
        input_path = Path(path).expanduser().resolve()
        return self.deserialize(input_path.read_text(encoding='utf-8'))


PARSED_DOCUMENT_JSON = ArtifactJsonSerializer(ParsedDocumentArtifact.from_dict)
CHUNKED_DOCUMENT_JSON = ArtifactJsonSerializer(ChunkedDocumentArtifact.from_dict)
EMBEDDED_DOCUMENT_JSON = ArtifactJsonSerializer(EmbeddedDocumentArtifact.from_dict)

__all__ = [
    'CHUNKED_DOCUMENT_JSON',
    'EMBEDDED_DOCUMENT_JSON',
    'PARSED_DOCUMENT_JSON',
    'ArtifactJsonSerializer',
]
