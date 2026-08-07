"""Parallel text, Markdown, and JSON serializers for parsed PDFs."""

from pathlib import Path
from typing import Protocol

from ai_tour_guide.ingestion.io import write_text_atomic
from ai_tour_guide.ingestion.pdf.markdown import render_markdown
from ai_tour_guide.ingestion.pdf.parser import ParsedPdf


class ParsedPdfSerializer(Protocol):
    """Common interface implemented by every parsed-PDF serializer."""

    def serialize(self, parsed_pdf: ParsedPdf) -> str: ...

    def write(self, parsed_pdf: ParsedPdf, path: str | Path) -> Path: ...


class ParsedPdfTextSerializer:
    """Serialize parsed PDF paragraphs as plain text."""

    def serialize(self, parsed_pdf: ParsedPdf) -> str:
        return f'{parsed_pdf.text}\n' if parsed_pdf.text else ''

    def write(self, parsed_pdf: ParsedPdf, path: str | Path) -> Path:
        return write_text_atomic(self.serialize(parsed_pdf), path)


class ParsedPdfMarkdownSerializer:
    """Serialize parsed PDF structure as Markdown."""

    def serialize(self, parsed_pdf: ParsedPdf) -> str:
        return render_markdown(parsed_pdf)

    def write(self, parsed_pdf: ParsedPdf, path: str | Path) -> Path:
        return write_text_atomic(self.serialize(parsed_pdf), path)


class ParsedPdfJsonSerializer:
    """Serialize parsed PDF structure as JSON."""

    def serialize(self, parsed_pdf: ParsedPdf) -> str:
        return parsed_pdf.to_json(indent=2, ensure_ascii=False) + '\n'

    def write(self, parsed_pdf: ParsedPdf, path: str | Path) -> Path:
        return write_text_atomic(self.serialize(parsed_pdf), path)


__all__ = [
    'ParsedPdfJsonSerializer',
    'ParsedPdfMarkdownSerializer',
    'ParsedPdfSerializer',
    'ParsedPdfTextSerializer',
]
