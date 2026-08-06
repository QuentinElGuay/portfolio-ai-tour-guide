"""Markdown exporter for structured tourism-guide PDFs."""

from pathlib import Path

from ai_tour_guide.ingestion.pdf.parser import ParsedPdf, ParsedSection


def render_markdown(parsed: ParsedPdf) -> str:
    blocks: list[str] = []

    for section in parsed.sections:
        _append_section_markdown(section, blocks)

    markdown = '\n\n'.join(blocks).strip()
    return f'{markdown}\n' if markdown else ''


def _append_section_markdown(
    section: ParsedSection,
    blocks: list[str],
) -> None:
    if section.title:
        level = min(max(section.level or 1, 1), 6)
        blocks.append(f'{"#" * level} {section.title.strip()}')

    blocks.extend(
        paragraph.text.strip()
        for paragraph in section.paragraphs
        if paragraph.text.strip()
    )

    for subsection in section.subsections:
        _append_section_markdown(subsection, blocks)


def write_markdown(parsed: ParsedPdf, destination: Path) -> Path:
    """Write parsed PDF content to a UTF-8 Markdown file."""
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_markdown(parsed), encoding='utf-8')
    return destination
