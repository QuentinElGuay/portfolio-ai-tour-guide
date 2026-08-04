from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Sequence

import httpx
import pymupdf
import pytest

from ai_tour_guide.ingestion.pdf.parser import (
    ParsedParagraph,
    ParsedPdf,
    ParsedSection,
    PdfDownloadError,
    PdfParseError,
    download_pdf,
    parse_pdf,
)

def _walk_sections(
    sections: Sequence[ParsedSection],
) -> Iterator[ParsedSection]:
    """Yield nested sections in document order."""
    for section in sections:
        yield section
        yield from _walk_sections(section.subsections)


def _pdf_bytes(*, pages: tuple[str, ...] = ("",)) -> bytes:
    """Create an in-memory PDF fixture using PyMuPDF."""
    with pymupdf.open() as document:
        for text in pages:
            page = document.new_page(width=300, height=300)
            if text:
                page.insert_text((20, 80), text, fontsize=11)
        return document.tobytes()


def test_download_pdf_writes_valid_response_atomically(tmp_path: Path) -> None:
    payload = _pdf_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://example.test/guide.pdf")
        return httpx.Response(
            200,
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


def test_download_pdf_rejects_non_pdf_content_type(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<html>not a pdf</html>",
        )

    destination = tmp_path / "guide.pdf"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PdfDownloadError, match="Expected a PDF"):
            download_pdf(
                "https://example.test/guide.pdf",
                destination,
                client=client,
            )

    assert not destination.exists()
    assert not list(tmp_path.glob("*.part"))


def test_download_pdf_rejects_invalid_signature(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"not really a pdf",
        )

    destination = tmp_path / "guide.pdf"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PdfDownloadError, match="not a valid PDF"):
            download_pdf(
                "https://example.test/guide.pdf",
                destination,
                client=client,
            )

    assert not destination.exists()
    assert not list(tmp_path.glob("*.part"))


def test_parse_pdf_returns_only_structured_sections(tmp_path: Path) -> None:
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
    assert result.source_page_count == 2
    assert result.page_count == 2
    assert not hasattr(result, "pages")
    assert not hasattr(result, "body_font_size")
    assert len(result.sections) == 1
    assert result.sections[0].title is None
    assert result.sections[0].page_start == 1
    assert result.sections[0].page_end == 2
    assert result.sections[0].paragraphs == (
        ParsedParagraph("Welcome to Brittany", 1, 1),
        ParsedParagraph("Explore Saint-Malo", 2, 2),
    )
    assert result.text == "Welcome to Brittany\n\nExplore Saint-Malo"


def test_parse_pdf_returns_empty_structure_for_blank_page(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    path.write_bytes(_pdf_bytes())

    result = parse_pdf(path)

    assert result.page_count == 1
    assert result.sections == ()
    assert result.text == ""


def test_parse_pdf_sorts_text_by_page_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "sorted.pdf"

    with pymupdf.open() as document:
        page = document.new_page(width=200, height=200)
        page.insert_text((20, 100), "Second section")
        page.insert_text((20, 50), "First section")
        document.save(path)

    result = parse_pdf(path)

    assert result.text.splitlines() == [
        "First section",
        "",
        "Second section",
    ]


def test_parse_pdf_detects_heading_levels_and_paragraph_pages(
    tmp_path: Path,
) -> None:
    path = tmp_path / "headings.pdf"

    with pymupdf.open() as document:
        page = document.new_page(width=400, height=500)
        page.insert_text((30, 50), "Brittany", fontsize=20, fontname="hebo")
        page.insert_text(
            (30, 100),
            "Brittany offers a varied coastline and historic towns.",
            fontsize=10,
        )
        page.insert_text((30, 160), "Saint-Malo", fontsize=15, fontname="hebo")
        page.insert_text(
            (30, 210),
            "The fortified city is a major tourism destination.",
            fontsize=10,
        )
        document.set_metadata({"title": "Discover Brittany"})
        document.save(path)

    result = parse_pdf(path)
    all_sections = tuple(_walk_sections(result.sections))

    assert result.title == "Discover Brittany"
    assert [(section.title, section.level) for section in all_sections] == [
        ("Brittany", 1),
        ("Saint-Malo", 2),
    ]

    assert len(result.sections) == 1
    brittany = result.sections[0]
    assert brittany.title == "Brittany"
    assert brittany.level == 1
    assert brittany.paragraphs == (
        ParsedParagraph(
            "Brittany offers a varied coastline and historic towns.",
            1,
            1,
        ),
    )

    assert len(brittany.subsections) == 1
    saint_malo = brittany.subsections[0]
    assert saint_malo.title == "Saint-Malo"
    assert saint_malo.level == 2
    assert saint_malo.paragraphs == (
        ParsedParagraph(
            "The fortified city is a major tourism destination.",
            1,
            1,
        ),
    )


def test_parse_pdf_preserves_original_pages_after_exclusions(tmp_path: Path) -> None:
    path = tmp_path / "excluded.pdf"
    path.write_bytes(
        _pdf_bytes(
            pages=(
                "Cover",
                "Tourism page two",
                "Tourism page three",
                "Company page",
            )
        )
    )

    result = parse_pdf(
        path,
        excluded_leading_pages=1,
        excluded_trailing_pages=1,
    )

    assert result.source_page_count == 4
    assert result.page_count == 2
    assert result.sections[0].page_start == 2
    assert result.sections[0].page_end == 3
    assert result.sections[0].paragraphs == (
        ParsedParagraph("Tourism page two", 2, 2),
        ParsedParagraph("Tourism page three", 3, 3),
    )
    assert "Cover" not in result.text
    assert "Company page" not in result.text


def test_parse_pdf_removes_repeated_headers_and_footers(tmp_path: Path) -> None:
    path = tmp_path / "margins.pdf"

    with pymupdf.open() as document:
        for index in range(4):
            page = document.new_page(width=300, height=300)
            page.insert_text((20, 15), "Running header", fontsize=8)
            page.insert_text((20, 100), f"Tourism content {index + 1}", fontsize=11)
            page.insert_text((20, 290), "Running footer", fontsize=8)
        document.save(path)

    result = parse_pdf(path)

    assert "Running header" not in result.text
    assert "Running footer" not in result.text
    assert "Tourism content 1" in result.text
    assert "Tourism content 4" in result.text


def test_parse_pdf_removes_ibanista_domain(tmp_path: Path) -> None:
    path = tmp_path / "fixture.pdf"

    with pymupdf.open() as document:
        page = document.new_page(width=300, height=300)
        page.insert_text((20, 50), "Welcome to Brittany")
        page.insert_text((20, 250), "ibanista.com")
        document.save(path)

    result = parse_pdf(path)

    assert result.text == "Welcome to Brittany"
    assert "ibanista.com" not in result.to_json().casefold()


def test_parsed_pdf_json_contains_only_canonical_structure(tmp_path: Path) -> None:
    parsed = ParsedPdf(
        source=tmp_path / "guide.pdf",
        source_page_count=12,
        page_count=10,
        metadata={"Title": "Découvrir la Bretagne"},
        sections=(
            ParsedSection(
                title="Saint-Malo",
                level=2,
                page_start=4,
                page_end=5,
                paragraphs=(
                    ParsedParagraph(
                        text="Une cité historique au bord de la mer.",
                        page_start=4,
                        page_end=4,
                    ),
                ),
            ),
        ),
    )

    data = json.loads(parsed.to_json())

    assert data["title"] == "Découvrir la Bretagne"
    assert data["sections"][0]["paragraphs"][0]["text"] == (
        "Une cité historique au bord de la mer."
    )
    assert data["sections"][0]["subsections"] == []
    assert "pages" not in data
    assert "body_font_size" not in data
    assert "text" not in data

    destination = parsed.write_json(tmp_path / "output" / "guide.json")
    assert destination.read_text(encoding="utf-8").endswith("\n")
    assert "Découvrir" in destination.read_text(encoding="utf-8")


def test_parse_pdf_raises_error_when_file_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(PdfParseError, match="PDF file does not exist"):
        parse_pdf(tmp_path / "missing.pdf")


def test_parse_pdf_rejects_malformed_pdf(tmp_path: Path) -> None:
    path = tmp_path / "malformed.pdf"
    path.write_bytes(b"%PDF-this-is-not-a-real-pdf")

    with pytest.raises(PdfParseError, match="Could not parse PDF"):
        parse_pdf(path)


def test_parse_pdf_rejects_exclusions_that_remove_every_page(
    tmp_path: Path,
) -> None:
    path = tmp_path / "single.pdf"
    path.write_bytes(_pdf_bytes(pages=("Only page",)))

    with pytest.raises(PdfParseError, match="remove the entire PDF"):
        parse_pdf(path, excluded_leading_pages=1)


def test_parse_pdf_merges_multiline_chapter_title(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multiline-heading.pdf"

    with pymupdf.open() as document:
        page = document.new_page(width=400, height=500)

        page.insert_text(
            (100, 70),
            "The region",
            fontsize=24,
        )
        page.insert_text(
            (130, 100),
            "and its",
            fontsize=24,
        )
        page.insert_text(
            (90, 130),
            "departments",
            fontsize=24,
        )
        page.insert_text(
            (50, 190),
            "Brittany is divided into several departments.",
            fontsize=11,
        )

        document.save(path)

    parsed = parse_pdf(path)

    titled_sections = [
        section
        for section in parsed.sections
        if section.title
    ]

    assert len(titled_sections) == 1

    section = titled_sections[0]

    assert section.title == "The region and its departments"
    assert section.level == 1
    assert section.page_start == 1
    assert section.page_end == 1
    assert section.text == (
        "Brittany is divided into several departments."
    )


def test_parse_pdf_detects_body_sized_bold_level_three_headings(
    tmp_path: Path,
) -> None:
    path = tmp_path / "three-heading-levels.pdf"

    with pymupdf.open() as document:
        chapter_page = document.new_page(width=600, height=800)
        chapter_page.insert_text(
            (60, 160),
            "Geography and climate",
            fontsize=28,
        )

        content_page = document.new_page(width=600, height=800)

        content_page.insert_text(
            (50, 70),
            "Geographical overview",
            fontsize=20,
            fontname="hebo",
        )

        content_page.insert_text(
            (50, 130),
            "Landscape and natural features",
            fontsize=12,
            fontname="hebo",
        )

        content_page.insert_text(
            (50, 175),
            (
                "Brittany, located in northwestern France, is a region "
                "renowned for its diverse and striking landscapes."
            ),
            fontsize=11,
        )

        content_page.insert_text(
            (50, 240),
            "Key features of each departments",
            fontsize=11,
            fontname="hebo",
        )

        content_page.insert_text(
            (50, 285),
            (
                "Ille-et-Vilaine: Home to the vibrant city of Rennes, "
                "the department combines urban and rural landscapes."
            ),
            fontsize=11,
        )

        document.save(path)

    parsed = parse_pdf(path)
    all_sections = tuple(_walk_sections(parsed.sections))
    sections_by_title = {
        section.title: section
        for section in all_sections
        if section.title
    }

    geography = sections_by_title["Geography and climate"]
    overview = sections_by_title["Geographical overview"]
    landscape = sections_by_title["Landscape and natural features"]
    key_features = sections_by_title["Key features of each departments"]

    assert geography.level == 1
    assert overview.level == 2
    assert landscape.level == 3
    assert key_features.level == 3

    assert parsed.sections == (geography,)
    assert geography.subsections == (overview,)
    assert overview.subsections == (landscape, key_features)

    assert landscape.paragraphs == (
        ParsedParagraph(
            "Brittany, located in northwestern France, is a region "
            "renowned for its diverse and striking landscapes.",
            2,
            2,
        ),
    )
    assert key_features.paragraphs == (
        ParsedParagraph(
            "Ille-et-Vilaine: Home to the vibrant city of Rennes, "
            "the department combines urban and rural landscapes.",
            2,
            2,
        ),
    )


def test_to_dict_serializes_nested_sections() -> None:
    level_three = ParsedSection(
        title="Key features of each departments",
        level=3,
        page_start=6,
        page_end=6,
        paragraphs=(),
    )

    level_two = ParsedSection(
        title="Departments of Brittany",
        level=2,
        page_start=6,
        page_end=6,
        paragraphs=(),
        subsections=(level_three,),
    )

    level_one = ParsedSection(
        title="The region and its departments",
        level=1,
        page_start=5,
        page_end=6,
        paragraphs=(),
        subsections=(level_two,),
    )

    result = level_one.to_dict()

    departments = result["subsections"][0]
    key_features = departments["subsections"][0]

    assert departments["level"] == 2
    assert key_features["level"] == 3
