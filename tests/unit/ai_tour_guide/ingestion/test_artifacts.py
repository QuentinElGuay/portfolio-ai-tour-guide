import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from ai_tour_guide.domain.chunks import Chunk, EmbeddedChunk
from ai_tour_guide.domain.documents import DocumentMetadata, DocumentRecord
from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.ingestion.artifacts import (
    ChunkedDocumentArtifact,
    EmbeddedDocumentArtifact,
    ParsedDocumentArtifact,
)
from ai_tour_guide.ingestion.cli import main
from ai_tour_guide.ingestion.config import ChunkingConfig
from ai_tour_guide.ingestion.constants import (
    DEFAULT_MAX_CHARS,
    DEFAULT_TARGET_CHARS,
)
from ai_tour_guide.ingestion.pdf.parser import (
    IngestionDocument,
    ParsedParagraph,
    ParsedPdf,
    ParsedSection,
)
from ai_tour_guide.ingestion.pdf.serializers import (
    ParsedPdfJsonSerializer,
    ParsedPdfMarkdownSerializer,
    ParsedPdfSerializer,
    ParsedPdfTextSerializer,
)
from ai_tour_guide.ingestion.serialization import (
    CHUNKED_DOCUMENT_JSON,
    EMBEDDED_DOCUMENT_JSON,
    PARSED_DOCUMENT_JSON,
    ArtifactJsonSerializer,
)


def _metadata() -> DocumentMetadata:
    return DocumentMetadata(
        title='A guide to Brittany',
        source_url='https://example.test/brittany.pdf',
        publisher='Tourism Board',
        publication_date=date(2026, 1, 2),
        authors=('Ada',),
        subject='Travel',
        keywords=('Brittany',),
        creator='Writer',
        producer='PDF tool',
        format='PDF 1.7',
        creation_date=datetime(2026, 1, 2, tzinfo=UTC),
        modification_date=datetime(2026, 1, 3, tzinfo=UTC),
        source_page_count=2,
        page_count=1,
    )


def _parsed_pdf() -> ParsedPdf:
    return ParsedPdf(
        metadata=_metadata(),
        sections=(
            ParsedSection(
                title='Coast',
                level=1,
                page_start=1,
                page_end=1,
                paragraphs=(ParsedParagraph('Visit Saint-Malo.', 1, 1),),
            ),
        ),
    )


def _document_record() -> DocumentRecord:
    return DocumentRecord(
        metadata=_metadata(),
        source_checksum='source-sha256',
        collection='tour-guides',
    )


def _chunk() -> Chunk:
    return Chunk(
        chunk_id='brittany:chunk-0000',
        document_title='A guide to Brittany',
        section_path=('A guide to Brittany', 'Coast'),
        section_id='coast',
        text='Visit Saint-Malo.',
        embedding_text=('A guide to Brittany\nCoast\n\nVisit Saint-Malo.'),
        page_start=1,
        page_end=1,
        chunk_index=0,
        character_count=18,
    )


def _parsed_artifact() -> ParsedDocumentArtifact:
    return ParsedDocumentArtifact(
        document=IngestionDocument(
            title='A guide to Brittany',
            source_url='https://example.test/brittany.pdf',
            collection='tour-guides',
            excluded_leading_pages=0,
            excluded_trailing_pages=0,
            publication_date=date(2026, 1, 2),
        ),
        source_checksum='source-sha256',
        parsed_pdf=_parsed_pdf(),
    )


@pytest.mark.parametrize(
    ('serializer', 'artifact'),
    [
        (PARSED_DOCUMENT_JSON, _parsed_artifact()),
        (
            CHUNKED_DOCUMENT_JSON,
            ChunkedDocumentArtifact(
                document=_document_record(),
                chunks=(_chunk(),),
                chunking=ChunkingConfig(
                    target_chars=DEFAULT_TARGET_CHARS,
                    max_chars=DEFAULT_MAX_CHARS,
                    section_chunk_min_depth=None,
                    section_chunk_max_depth=None,
                ),
            ),
        ),
        (
            EMBEDDED_DOCUMENT_JSON,
            EmbeddedDocumentArtifact(
                document=_document_record(),
                chunks=(
                    EmbeddedChunk(
                        chunk=_chunk(),
                        embedding=(0.1, 0.2),
                        embedding_input_sha256='embedding-sha256',
                    ),
                ),
                chunking=(
                    ChunkingConfig(
                        target_chars=DEFAULT_TARGET_CHARS,
                        max_chars=DEFAULT_MAX_CHARS,
                        section_chunk_min_depth=None,
                        section_chunk_max_depth=None,
                    )
                ),
                embedding=EmbeddingMetadata(
                    provider='fastembed',
                    model_name='test-model',
                    dimensions=2,
                    normalized=True,
                ),
            ),
        ),
    ],
)
def test_stage_artifacts_round_trip_as_self_contained_json(
    tmp_path: Path,
    serializer: ArtifactJsonSerializer[Any],
    artifact: Any,
) -> None:
    output_path = tmp_path / 'artifact.json'

    serializer.write(artifact, output_path)

    assert serializer.read(output_path) == artifact
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['schema_version'] == 1
    assert 'document' in payload


@pytest.mark.parametrize(
    'serializer',
    [
        ParsedPdfTextSerializer(),
        ParsedPdfMarkdownSerializer(),
        ParsedPdfJsonSerializer(),
    ],
)
def test_parsed_pdf_serializers_share_serialize_and_write_interface(
    tmp_path: Path,
    serializer: ParsedPdfSerializer,
) -> None:
    parsed_pdf = _parsed_pdf()
    output_path = tmp_path / 'parsed-output'

    serialized = serializer.serialize(parsed_pdf)
    written_path = serializer.write(parsed_pdf, output_path)

    assert written_path == output_path.resolve()
    assert written_path.read_text(encoding='utf-8') == serialized


def test_artifact_reader_rejects_the_wrong_stage_type() -> None:
    content = PARSED_DOCUMENT_JSON.serialize(_parsed_artifact())

    with pytest.raises(ValueError, match='chunked_document'):
        CHUNKED_DOCUMENT_JSON.deserialize(content)


def test_chunk_command_reads_and_writes_self_contained_artifacts(
    tmp_path: Path,
) -> None:
    parsed_path = tmp_path / 'guide.parsed.json'
    chunked_path = tmp_path / 'guide.chunked.json'
    PARSED_DOCUMENT_JSON.write(_parsed_artifact(), parsed_path)

    result = CliRunner().invoke(
        main,
        [
            'chunk',
            str(parsed_path),
            '--output',
            str(chunked_path),
            '--target-chars',
            '100',
            '--max-chars',
            '200',
        ],
    )

    assert result.exit_code == 0
    artifact = CHUNKED_DOCUMENT_JSON.read(chunked_path)
    assert artifact.document.collection == 'tour-guides'
    assert artifact.document.source_checksum == 'source-sha256'
    assert len(artifact.chunks) == 1
    assert artifact.chunking == ChunkingConfig(100, 200, None, None)
