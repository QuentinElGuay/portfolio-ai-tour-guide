from __future__ import annotations

from pathlib import Path

from ai_tour_guide.ingestion.pdf.markdown import render_markdown, write_markdown
from ai_tour_guide.ingestion.pdf.parser import (
    ParsedParagraph,
    ParsedPdf,
    ParsedSection,
)


def _parsed_pdf(tmp_path: Path) -> ParsedPdf:
    return ParsedPdf(
        source=tmp_path / 'guide.pdf',
        source_page_count=8,
        page_count=6,
        metadata={'Title': 'Discover Brittany'},
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


def test_render_markdown_uses_paragraph_text(tmp_path: Path) -> None:
    markdown = render_markdown(_parsed_pdf(tmp_path))

    assert markdown == (
        '# Brittany\n\n'
        'A coastal region with a strong cultural identity.\n\n'
        '## Saint-Malo\n\n'
        'Explore the fortified old town.\n'
    )


def test_write_markdown_creates_parent_directories(tmp_path: Path) -> None:
    destination = write_markdown(
        _parsed_pdf(tmp_path),
        tmp_path / 'nested' / 'guide.md',
    )

    assert destination == (tmp_path / 'nested' / 'guide.md').resolve()
    assert destination.read_text(encoding='utf-8').startswith('# Brittany')


def test_render_markdown_handles_untitled_content(tmp_path: Path) -> None:
    parsed = ParsedPdf(
        source=tmp_path / 'guide.pdf',
        source_page_count=1,
        page_count=1,
        metadata={},
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
