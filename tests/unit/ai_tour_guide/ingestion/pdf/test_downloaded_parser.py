from pathlib import Path

import pymupdf

from ai_tour_guide.ingestion.pdf.parser import (
    IngestionDocument,
    parse_downloaded_pdf,
)


def test_parse_downloaded_pdf_uses_the_existing_file(tmp_path: Path) -> None:
    pdf_path = tmp_path / 'guide.pdf'
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), 'Visit Brittany')
        pdf.save(pdf_path)

    document = IngestionDocument(
        title='Brittany guide',
        source_url='https://example.com/guide.pdf',
        excluded_leading_pages=0,
        excluded_trailing_pages=0,
    )

    result = parse_downloaded_pdf(pdf_path, document=document)

    assert result.metadata.source_url == document.source_url
    assert result.metadata.source_page_count == 1
    assert result.metadata.page_count == 1
