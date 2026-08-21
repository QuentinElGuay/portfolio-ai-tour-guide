from pathlib import Path

from ai_tour_guide.domain.documents import DocumentMetadata
from ai_tour_guide.ingestion.pdf.markdown import render_markdown, write_markdown
from ai_tour_guide.ingestion.pdf.parser import (
    ParsedParagraph,
    ParsedPdf,
    ParsedSection,
)


def _metadata(
    *,
    title: str = 'Discover Brittany',
    source_page_count: int = 8,
    page_count: int = 6,
) -> DocumentMetadata:
    return DocumentMetadata(
        title=title,
        source_url='https://example.test/guide.pdf',
        publisher=None,
        publication_date=None,
        authors=(),
        subject=None,
        keywords=(),
        creator=None,
        producer=None,
        format='PDF 1.7',
        creation_date=None,
        modification_date=None,
        source_page_count=source_page_count,
        page_count=page_count,
    )


def _parsed_pdf() -> ParsedPdf:
    return ParsedPdf(
        metadata=_metadata(),
        sections=(
            ParsedSection(
                title='Brittany',
                level=1,
                page_start=2,
                page_end=4,
                paragraphs=(
                    ParsedParagraph(
                        text='A coastal region with a strong cultural identity.',
                        page_start=2,
                        page_end=2,
                    ),
                ),
            ),
            ParsedSection(
                title='Saint-Malo',
                level=2,
                page_start=4,
                page_end=5,
                paragraphs=(
                    ParsedParagraph(
                        text='Explore the fortified old town.',
                        page_start=4,
                        page_end=4,
                    ),
                ),
            ),
        ),
    )


def test_render_markdown_uses_paragraph_text() -> None:
    """Verify that render markdown uses paragraph text."""
    markdown = render_markdown(_parsed_pdf())

    assert markdown == (
        '# Brittany\n\n'
        'A coastal region with a strong cultural identity.\n\n'
        '## Saint-Malo\n\n'
        'Explore the fortified old town.\n'
    )


def test_write_markdown_creates_parent_directories(tmp_path: Path) -> None:
    """Verify that write markdown creates parent directories."""
    destination = write_markdown(
        _parsed_pdf(),
        tmp_path / 'nested' / 'guide.md',
    )

    assert destination == (tmp_path / 'nested' / 'guide.md').resolve()
    assert destination.read_text(encoding='utf-8').startswith('# Brittany')


def test_render_markdown_handles_untitled_content() -> None:
    """Verify that render markdown handles untitled content."""
    parsed = ParsedPdf(
        metadata=_metadata(source_page_count=1, page_count=1),
        sections=(
            ParsedSection(
                title=None,
                level=None,
                page_start=1,
                page_end=1,
                paragraphs=(ParsedParagraph('Introduction', 1, 1),),
            ),
        ),
    )

    assert render_markdown(parsed) == 'Introduction\n'
