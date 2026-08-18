"""Typed values exchanged between independent ingestion stages."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from ai_tour_guide.domain.chunks import Chunk, EmbeddedChunk
from ai_tour_guide.domain.documents import DocumentMetadata, DocumentRecord
from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.ingestion.config import ChunkingConfig
from ai_tour_guide.ingestion.pdf.parser import (
    IngestionDocument,
    ParsedParagraph,
    ParsedPdf,
    ParsedSection,
)

ARTIFACT_SCHEMA_VERSION = 1


def _require_mapping(value: object, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f'{field_name} must be a JSON object')
    return value


def _require_list(value: object, *, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f'{field_name} must be a JSON array')
    return value


def _validate_envelope(data: Mapping[str, Any], *, artifact_type: str) -> None:
    if data.get('artifact_type') != artifact_type:
        raise ValueError(f'Expected a {artifact_type!r} artifact')
    if data.get('schema_version') != ARTIFACT_SCHEMA_VERSION:
        raise ValueError(
            f'Unsupported artifact schema version: {data.get("schema_version")!r}'
        )


def _ingestion_document_to_dict(document: IngestionDocument) -> dict[str, Any]:
    return {
        'title': document.title,
        'source_url': document.source_url,
        'collection': document.collection,
        'excluded_leading_pages': document.excluded_leading_pages,
        'excluded_trailing_pages': document.excluded_trailing_pages,
        'authors': document.authors,
        'keywords': document.keywords,
        'publisher': document.publisher,
        'publication_date': (
            document.publication_date.isoformat()
            if document.publication_date is not None
            else None
        ),
        'ignored_text_patterns': [
            pattern.pattern for pattern in document.ignored_text_patterns
        ],
    }


def _ingestion_document_from_dict(data: Mapping[str, Any]) -> IngestionDocument:
    return IngestionDocument.from_dict(dict(data))


def _metadata_to_dict(metadata: DocumentMetadata) -> dict[str, Any]:
    return {
        'title': metadata.title,
        'source_url': metadata.source_url,
        'publisher': metadata.publisher,
        'publication_date': (
            metadata.publication_date.isoformat()
            if metadata.publication_date is not None
            else None
        ),
        'authors': list(metadata.authors),
        'subject': metadata.subject,
        'keywords': list(metadata.keywords),
        'creator': metadata.creator,
        'producer': metadata.producer,
        'format': metadata.format,
        'creation_date': (
            metadata.creation_date.isoformat()
            if metadata.creation_date is not None
            else None
        ),
        'modification_date': (
            metadata.modification_date.isoformat()
            if metadata.modification_date is not None
            else None
        ),
        'source_page_count': metadata.source_page_count,
        'page_count': metadata.page_count,
    }


def _metadata_from_dict(data: Mapping[str, Any]) -> DocumentMetadata:
    publication_date = data.get('publication_date')
    creation_date = data.get('creation_date')
    modification_date = data.get('modification_date')

    return DocumentMetadata(
        title=str(data['title']),
        source_url=str(data['source_url']),
        publisher=data.get('publisher'),
        publication_date=(
            date.fromisoformat(str(publication_date))
            if publication_date is not None
            else None
        ),
        authors=tuple(str(value) for value in data.get('authors', [])),
        subject=data.get('subject'),
        keywords=tuple(str(value) for value in data.get('keywords', [])),
        creator=data.get('creator'),
        producer=data.get('producer'),
        format=data.get('format'),
        creation_date=(
            datetime.fromisoformat(str(creation_date))
            if creation_date is not None
            else None
        ),
        modification_date=(
            datetime.fromisoformat(str(modification_date))
            if modification_date is not None
            else None
        ),
        source_page_count=int(data['source_page_count']),
        page_count=int(data['page_count']),
    )


def _paragraph_from_dict(data: Mapping[str, Any]) -> ParsedParagraph:
    return ParsedParagraph(
        text=str(data['text']),
        page_start=int(data['page_start']),
        page_end=int(data['page_end']),
    )


def _section_from_dict(data: Mapping[str, Any]) -> ParsedSection:
    paragraphs = _require_list(data.get('paragraphs'), field_name='paragraphs')
    subsections = _require_list(data.get('subsections'), field_name='subsections')
    level = data.get('level')

    return ParsedSection(
        title=data.get('title'),
        level=int(level) if level is not None else None,
        page_start=int(data['page_start']),
        page_end=int(data['page_end']),
        paragraphs=tuple(
            _paragraph_from_dict(_require_mapping(paragraph, field_name='paragraph'))
            for paragraph in paragraphs
        ),
        subsections=tuple(
            _section_from_dict(_require_mapping(section, field_name='subsection'))
            for section in subsections
        ),
    )


def _parsed_pdf_to_dict(parsed_pdf: ParsedPdf) -> dict[str, Any]:
    return {
        'metadata': _metadata_to_dict(parsed_pdf.metadata),
        'sections': [section.to_dict() for section in parsed_pdf.sections],
    }


def _parsed_pdf_from_dict(data: Mapping[str, Any]) -> ParsedPdf:
    sections = _require_list(data.get('sections'), field_name='sections')
    return ParsedPdf(
        metadata=_metadata_from_dict(
            _require_mapping(data.get('metadata'), field_name='metadata')
        ),
        sections=tuple(
            _section_from_dict(_require_mapping(section, field_name='section'))
            for section in sections
        ),
    )


def _document_record_to_dict(document: DocumentRecord) -> dict[str, Any]:
    return {
        'metadata': _metadata_to_dict(document.metadata),
        'source_checksum': document.source_checksum,
        'collection': document.collection,
        'version': document.version,
    }


def _document_record_from_dict(data: Mapping[str, Any]) -> DocumentRecord:
    return DocumentRecord(
        metadata=_metadata_from_dict(
            _require_mapping(data.get('metadata'), field_name='metadata')
        ),
        source_checksum=str(data['source_checksum']),
        collection=data.get('collection'),
        version=data.get('version'),
    )


def _embedding_metadata_to_dict(metadata: EmbeddingMetadata) -> dict[str, Any]:
    return {
        'provider': metadata.provider,
        'model_name': metadata.model_name,
        'model_revision': metadata.model_revision,
        'dimensions': metadata.dimensions,
        'normalized': metadata.normalized,
        'distance_metric': metadata.distance_metric,
    }


def _embedding_metadata_from_dict(data: Mapping[str, Any]) -> EmbeddingMetadata:
    normalized = data['normalized']
    if not isinstance(normalized, bool):
        raise TypeError('embedding.normalized must be a boolean')

    return EmbeddingMetadata(
        provider=str(data['provider']),
        model_name=str(data['model_name']),
        model_revision=str(data.get('model_revision', 'default')),
        dimensions=int(data['dimensions']),
        normalized=normalized,
        distance_metric=str(data.get('distance_metric', 'cosine')),
    )


@dataclass(frozen=True, slots=True)
class DownloadedPdf:
    """One downloaded source PDF held in memory."""

    document: IngestionDocument
    content: bytes
    source_checksum: str


@dataclass(frozen=True, slots=True)
class ParsedDocumentArtifact:
    """Output of the PDF parsing stage."""

    document: IngestionDocument
    source_checksum: str
    parsed_pdf: ParsedPdf

    def to_dict(self) -> dict[str, Any]:
        return {
            'artifact_type': 'parsed_document',
            'schema_version': ARTIFACT_SCHEMA_VERSION,
            'document': _ingestion_document_to_dict(self.document),
            'source_checksum': self.source_checksum,
            'parsed_pdf': _parsed_pdf_to_dict(self.parsed_pdf),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ParsedDocumentArtifact:
        _validate_envelope(data, artifact_type='parsed_document')
        return cls(
            document=_ingestion_document_from_dict(
                _require_mapping(data.get('document'), field_name='document')
            ),
            source_checksum=str(data['source_checksum']),
            parsed_pdf=_parsed_pdf_from_dict(
                _require_mapping(data.get('parsed_pdf'), field_name='parsed_pdf')
            ),
        )


@dataclass(frozen=True, slots=True)
class ChunkedDocumentArtifact:
    """Persistence-ready document plus unembedded retrieval chunks."""

    document: DocumentRecord
    chunks: tuple[Chunk, ...]
    chunking: ChunkingConfig

    def to_dict(self) -> dict[str, Any]:
        return {
            'artifact_type': 'chunked_document',
            'schema_version': ARTIFACT_SCHEMA_VERSION,
            'document': _document_record_to_dict(self.document),
            'chunks': [chunk.to_dict() for chunk in self.chunks],
            'chunking': self.chunking.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ChunkedDocumentArtifact:
        _validate_envelope(data, artifact_type='chunked_document')
        chunks = _require_list(data.get('chunks'), field_name='chunks')
        return cls(
            document=_document_record_from_dict(
                _require_mapping(data.get('document'), field_name='document')
            ),
            chunks=tuple(
                Chunk.from_dict(_require_mapping(chunk, field_name='chunk'))
                for chunk in chunks
            ),
            chunking=ChunkingConfig.from_dict(
                dict(_require_mapping(data.get('chunking'), field_name='chunking'))
            ),
        )


@dataclass(frozen=True, slots=True)
class EmbeddedDocumentArtifact:
    """Complete input required by the knowledge-base loading stage."""

    document: DocumentRecord
    chunks: tuple[EmbeddedChunk, ...]
    chunking: ChunkingConfig
    embedding: EmbeddingMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            'artifact_type': 'embedded_document',
            'schema_version': ARTIFACT_SCHEMA_VERSION,
            'document': _document_record_to_dict(self.document),
            'chunks': [
                {
                    'chunk': chunk.chunk.to_dict(),
                    'embedding': list(chunk.embedding),
                    'embedding_input_sha256': chunk.embedding_input_sha256,
                }
                for chunk in self.chunks
            ],
            'chunking': self.chunking.to_dict(),
            'embedding': _embedding_metadata_to_dict(self.embedding),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EmbeddedDocumentArtifact:
        _validate_envelope(data, artifact_type='embedded_document')
        chunks = _require_list(data.get('chunks'), field_name='chunks')
        embedded_chunks: list[EmbeddedChunk] = []

        for value in chunks:
            chunk_data = _require_mapping(value, field_name='embedded chunk')
            embedded_chunks.append(
                EmbeddedChunk(
                    chunk=Chunk.from_dict(
                        _require_mapping(chunk_data.get('chunk'), field_name='chunk')
                    ),
                    embedding=tuple(
                        float(item)
                        for item in _require_list(
                            chunk_data.get('embedding'),
                            field_name='embedding',
                        )
                    ),
                    embedding_input_sha256=str(chunk_data['embedding_input_sha256']),
                )
            )

        return cls(
            document=_document_record_from_dict(
                _require_mapping(data.get('document'), field_name='document')
            ),
            chunks=tuple(embedded_chunks),
            chunking=ChunkingConfig.from_dict(
                dict(
                    _require_mapping(
                        data.get('chunking'),
                        field_name='chunking',
                    )
                )
            ),
            embedding=_embedding_metadata_from_dict(
                _require_mapping(data.get('embedding'), field_name='embedding')
            ),
        )


__all__ = [
    'ARTIFACT_SCHEMA_VERSION',
    'ChunkedDocumentArtifact',
    'DownloadedPdf',
    'EmbeddedDocumentArtifact',
    'ParsedDocumentArtifact',
]
