from pathlib import Path

import pymupdf

from ai_tour_guide.ingestion.pdf.parser import (
    IngestionDocument,
    parse_downloaded_pdf,
    parse_pdf_bytes,
)


def test_parse_downloaded_pdf_uses_the_existing_file(tmp_path: Path) -> None:
    """Verify that parse downloaded pdf uses the existing file."""
    pdf_path = tmp_path / 'guide.pdf'
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), 'Visit Brittany')
        pdf.save(pdf_path)

    document = IngestionDocument(
        title='Brittany guide',
        destination='Brittany',
        source_url='https://example.com/guide.pdf',
        excluded_leading_pages=0,
        excluded_trailing_pages=0,
    )

    result = parse_downloaded_pdf(pdf_path, document=document)

    assert result.metadata.source_url == document.source_url
    assert result.metadata.source_page_count == 1
    assert result.metadata.page_count == 1


def test_parse_pdf_bytes_uses_no_intermediary_file(tmp_path: Path) -> None:
    """Verify that parse pdf bytes uses no intermediary file."""
    pdf_path = tmp_path / 'source.pdf'
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), 'Visit Brittany')
        pdf.save(pdf_path)

    content = pdf_path.read_bytes()
    pdf_path.unlink()
    document = IngestionDocument(
        title='Brittany guide',
        destination='Brittany',
        source_url='https://example.com/guide.pdf',
        excluded_leading_pages=0,
        excluded_trailing_pages=0,
    )

    result = parse_pdf_bytes(content, document=document)

    assert not pdf_path.exists()
    assert result.text == 'Visit Brittany'
