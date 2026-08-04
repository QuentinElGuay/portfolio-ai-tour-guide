from pathlib import Path

from ai_tour_guide.ingestion.pdf.markdown import render_markdown
from ai_tour_guide.ingestion.pdf.parser import ParsedPdf, ParsedSection


def test_render_markdown_uses_section_heading_levels() -> None:
    parsed = ParsedPdf(
        source=Path("guide.pdf"),
        source_page_count=4,
        page_count=2,
        pages=("Brittany", "Saint-Malo"),
        lines=(),
        sections=(
            ParsedSection(
                title="Brittany",
                level=1,
                page_start=1,
                page_end=2,
                paragraphs=("A region in north-western France.",),
            ),
            ParsedSection(
                title="Saint-Malo",
                level=2,
                page_start=2,
                page_end=2,
                paragraphs=("A historic walled port city.",),
            ),
        ),
        body_font_size=10.0,
    )

    assert render_markdown(parsed) == (
        "# Brittany\n\n"
        "A region in north-western France.\n\n"
        "## Saint-Malo\n\n"
        "A historic walled port city.\n"
    )

import pymupdf

from ai_tour_guide.ingestion.pdf.parser import parse_pdf


def test_parse_pdf_builds_markdown_ready_sections(tmp_path: Path) -> None:
    pdf_path = tmp_path / "guide.pdf"

    with pymupdf.open() as document:
        page = document.new_page(width=400, height=500)
        page.insert_text((40, 60), "Discover Brittany", fontsize=24)
        page.insert_text((40, 100), "A beautiful region in France.", fontsize=10)
        page.insert_text((40, 160), "Saint-Malo", fontsize=16)
        page.insert_text((40, 200), "Explore the historic walled city.", fontsize=10)
        document.save(pdf_path)

    parsed = parse_pdf(pdf_path)

    assert [section.title for section in parsed.sections] == [
        "Discover Brittany",
        "Saint-Malo",
    ]
    assert [section.level for section in parsed.sections] == [1, 2]
    assert render_markdown(parsed).startswith(
        "# Discover Brittany\n\nA beautiful region in France.\n\n## Saint-Malo"
    )
