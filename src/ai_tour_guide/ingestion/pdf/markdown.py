"""Markdown exporter for parsed PDF tourism guides."""

from __future__ import annotations

from pathlib import Path

from ai_tour_guide.ingestion.pdf.parser import ParsedPdf


def render_markdown(parsed: ParsedPdf) -> str:
    """Render a parsed PDF as Markdown with inferred heading levels."""
    blocks: list[str] = []

    for section in parsed.sections:
        if section.title:
            level = min(max(section.level or 1, 1), 6)
            blocks.append(f"{'#' * level} {section.title.strip()}")

        blocks.extend(
            paragraph.strip()
            for paragraph in section.paragraphs
            if paragraph.strip()
        )

    markdown = "\n\n".join(blocks).strip()
    return f"{markdown}\n" if markdown else ""


def write_markdown(parsed: ParsedPdf, destination: Path) -> Path:
    """Write parsed PDF content to a UTF-8 Markdown file."""
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_markdown(parsed), encoding="utf-8")
    return destination
