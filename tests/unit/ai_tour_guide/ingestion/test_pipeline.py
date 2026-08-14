from collections.abc import Sequence

import numpy as np
import pymupdf

from ai_tour_guide.embedding import EmbeddingMetadata
from ai_tour_guide.ingestion.artifacts import DownloadedPdf
from ai_tour_guide.ingestion.pdf.parser import IngestionDocument
from ai_tour_guide.ingestion.pipeline import (
    chunk_document_stage,
    embed_document_stage,
    parse_pdf_stage,
)


class _FakeEmbedder:
    @property
    def metadata(self) -> EmbeddingMetadata:
        return EmbeddingMetadata(
            provider='test',
            model_name='test-model',
            dimensions=2,
            normalized=False,
        )

    def embed_documents(
        self,
        texts: Sequence[str],
        *,
        batch_size: int,
    ) -> np.ndarray:
        assert batch_size == 8
        return np.asarray([[float(index), 1.0] for index, _ in enumerate(texts)])

    def embed_query(self, text: str) -> np.ndarray:
        return np.asarray([0.0, 1.0])


def test_typed_stages_compose_without_intermediate_files() -> None:
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), 'Visit Saint-Malo.')
        pdf_bytes = pdf.tobytes()

    document = IngestionDocument(
        title='A guide to Brittany',
        source_url='https://example.test/brittany.pdf',
        collection='tour-guides',
        excluded_leading_pages=0,
        excluded_trailing_pages=0,
    )

    parsed = parse_pdf_stage(
        DownloadedPdf(
            document=document,
            content=pdf_bytes,
            source_checksum='source-sha256',
        )
    )
    chunked = chunk_document_stage(
        parsed,
        target_chars=100,
        max_chars=200,
        min_depth=1,
        max_depth=2,
    )
    embedded = embed_document_stage(
        chunked,
        embedder=_FakeEmbedder(),
        batch_size=8,
    )

    assert embedded.document.collection == 'tour-guides'
    assert embedded.document.source_checksum == 'source-sha256'
    assert embedded.document.metadata.source_url == document.source_url
    assert len(embedded.chunks) == 1
    assert embedded.chunks[0].chunk.text == 'Visit Saint-Malo.'
    assert embedded.chunks[0].embedding == (0.0, 1.0)
    assert embedded.embedding.dimensions == 2
