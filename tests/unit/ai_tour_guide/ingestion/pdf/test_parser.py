from __future__ import annotations

from pathlib import Path

import httpx
import pymupdf
import pytest

from ai_tour_guide.ingestion.pdf.parser import (
    PdfDownloadError,
    PdfParseError,
    download_pdf,
    parse_pdf,
)


def _pdf_bytes(
    *,
    pages: tuple[str, ...] = ("",),
) -> bytes:
    """Create an in-memory PDF fixture using PyMuPDF."""
    with pymupdf.open() as document:
        for text in pages:
            page = document.new_page(width=200, height=200)

            if text:
                page.insert_text(
                    point=(20, 50),
                    text=text,
                    fontsize=11,
                )

        return document.tobytes()


def test_download_pdf_writes_valid_response_atomically(
    tmp_path: Path,
) -> None:
    payload = _pdf_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://example.test/guide.pdf")

        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/pdf"},
            content=payload,
        )

    destination = tmp_path / "downloads" / "guide.pdf"

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = download_pdf(
            "https://example.test/guide.pdf",
            destination,
            client=client,
        )

    assert result == destination.resolve()
    assert result.read_bytes() == payload
    assert not list(destination.parent.glob("*.part"))


def test_download_pdf_rejects_non_pdf_content_type(
    tmp_path: Path,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/html"},
            content=b"<html>not a pdf</html>",
        )

    destination = tmp_path / "guide.pdf"

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            PdfDownloadError,
            match="Expected a PDF",
        ):
            download_pdf(
                "https://example.test/guide.pdf",
                destination,
                client=client,
            )

    assert not destination.exists()
    assert not list(tmp_path.glob("*.part"))


def test_download_pdf_rejects_invalid_signature(
    tmp_path: Path,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/pdf"},
            content=b"not really a pdf",
        )

    destination = tmp_path / "guide.pdf"

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            PdfDownloadError,
            match="not a valid PDF",
        ):
            download_pdf(
                "https://example.test/guide.pdf",
                destination,
                client=client,
            )

    assert not destination.exists()
    assert not list(tmp_path.glob("*.part"))


def test_parse_pdf_extracts_pages(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fixture.pdf"
    path.write_bytes(
        _pdf_bytes(
            pages=(
                "Welcome to Brittany",
                "Explore Saint-Malo",
            )
        )
    )

    result = parse_pdf(path)

    assert result.source == path.resolve()
    assert result.page_count == 2
    assert result.pages == (
        "Welcome to Brittany",
        "Explore Saint-Malo",
    )
    assert result.text == ("Welcome to Brittany\n\nExplore Saint-Malo")


def test_parse_pdf_returns_empty_text_for_blank_page(
    tmp_path: Path,
) -> None:
    path = tmp_path / "blank.pdf"
    path.write_bytes(_pdf_bytes(pages=("",)))

    result = parse_pdf(path)

    assert result.page_count == 1
    assert result.pages == ("",)
    assert result.text == ""


def test_parse_pdf_sorts_text_by_page_coordinates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sorted.pdf"

    with pymupdf.open() as document:
        page = document.new_page(width=200, height=200)
        page.insert_text((20, 100), "Second section")
        page.insert_text((20, 50), "First section")
        document.save(path)

    result = parse_pdf(path)

    non_empty_lines = [
        line
        for line in result.pages[0].splitlines()
        if line
    ]

    assert non_empty_lines == [
        "First section",
        "Second section",
    ]


def test_parse_pdf_raises_error_when_file_does_not_exist(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing.pdf"

    with pytest.raises(
        PdfParseError,
        match="PDF file does not exist",
    ):
        parse_pdf(path)


def test_parse_pdf_rejects_malformed_pdf(
    tmp_path: Path,
) -> None:
    path = tmp_path / "malformed.pdf"
    path.write_bytes(b"%PDF-this-is-not-a-real-pdf")

    with pytest.raises(
        PdfParseError,
        match="Could not parse PDF",
    ):
        parse_pdf(path)


def test_parse_pdf_removes_ibanista_domain(tmp_path: Path) -> None:
    path = tmp_path / "fixture.pdf"

    with pymupdf.open() as document:
        page = document.new_page(width=300, height=300)
        page.insert_text((20, 50), "Welcome to Brittany")
        page.insert_text((20, 250), "ibanista.com")
        document.save(path)

    result = parse_pdf(path)

    assert result.pages == ("Welcome to Brittany",)
    assert "ibanista.com" not in result.text.casefold()
    assert all(
        "ibanista.com" not in line.text.casefold()
        for line in result.lines
    )