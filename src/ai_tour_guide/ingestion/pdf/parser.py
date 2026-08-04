"""Core PDF download and parsing logic."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import httpx
import pymupdf

MAX_HORIZONTAL_GAP_FACTOR = 3.0
MIN_VERTICAL_OVERLAP_RATIO = 0.6
IGNORED_TEXT_PATTERNS = (
    re.compile(
        r"(?:https?://)?(?:www\.)?ibanista\s*\.\s*com/?",
        flags=re.IGNORECASE,
    ),
)

class PdfDownloadError(RuntimeError):
    """Raised when a PDF cannot be downloaded or validated."""


class PdfParseError(RuntimeError):
    """Raised when a downloaded file cannot be parsed as a PDF."""


@dataclass(frozen=True, slots=True)
class TextLine:
    """A line of text extracted from a PDF page."""

    page_number: int
    block_number: int
    line_number: int
    text: str
    font: str
    font_size: float
    is_bold: bool
    bbox: tuple[float, float, float, float]
    page_height: float


@dataclass(frozen=True, slots=True)
class ParsedSection:
    """A section inferred from PDF typography.

    ``title`` and ``level`` describe the Markdown heading. ``paragraphs``
    preserves the section body without encoding an output format in the parser.
    """

    title: str | None
    level: int | None
    page_start: int
    page_end: int
    paragraphs: tuple[str, ...]

    @property
    def text(self) -> str:
        """Return the section body as plain text."""
        return "\n\n".join(self.paragraphs)

    @property
    def content(self) -> str:
        """Return the title and body as embedding-ready text."""
        if self.title and self.text:
            return f"{self.title}\n\n{self.text}"

        return self.title or self.text


@dataclass(frozen=True, slots=True)
class ParsedPdf:
    """Structured result returned by :func:`parse_pdf`."""

    source: Path
    source_page_count: int
    page_count: int
    pages: tuple[str, ...]
    lines: tuple[TextLine, ...]
    sections: tuple[ParsedSection, ...]
    body_font_size: float | None

    @property
    def text(self) -> str:
        """Return retained page text separated by blank lines."""
        return "\n\n".join(self.pages)


def download_pdf(
    url: str,
    destination: Path,
    *,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> Path:
    """Download *url* atomically to *destination* and validate its signature.

    A temporary file is used so a failed or interrupted download does not
    leave a partially written destination file behind.
    """
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    owns_client = client is None
    http_client = client or httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout_seconds),
        headers={"User-Agent": "portfolio-ai-tour-guide/0.1"},
    )

    temp_path: Path | None = None

    try:
        with http_client.stream("GET", url) as response:
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()
            if content_type and "pdf" not in content_type:
                raise PdfDownloadError(
                    f"Expected a PDF response, received {content_type!r}."
                )

            with NamedTemporaryFile(
                mode="wb",
                delete=False,
                dir=destination.parent,
                suffix=".part",
            ) as temp_file:
                temp_path = Path(temp_file.name)

                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    temp_file.write(chunk)

        if temp_path.stat().st_size == 0:
            raise PdfDownloadError("The downloaded file is empty.")

        with temp_path.open("rb") as file_handle:
            if file_handle.read(5) != b"%PDF-":
                raise PdfDownloadError(
                    "The downloaded file is not a valid PDF."
                )

        temp_path.replace(destination)
        return destination

    except (httpx.HTTPError, OSError) as exc:
        raise PdfDownloadError(
            f"Could not download PDF from {url}: {exc}"
        ) from exc

    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

        if owns_client:
            http_client.close()


def parse_pdf(
    path: Path,
    *,
    excluded_leading_pages: int = 0,
    excluded_trailing_pages: int = 0,
) -> ParsedPdf:
    """Extract tourism content while excluding trailing company pages."""
    path = path.expanduser().resolve()

    if not path.is_file():
        raise PdfParseError(f"PDF file does not exist: {path}")

    if excluded_leading_pages < 0:
        raise ValueError("excluded_leading_pages cannot be negative")

    if excluded_trailing_pages < 0:
        raise ValueError("excluded_trailing_pages cannot be negative")

    try:
        with pymupdf.open(path) as document:
            if document.needs_pass and document.authenticate("") <= 0:
                raise PdfParseError(
                    "The PDF is encrypted and cannot be opened."
                )

            source_page_count = document.page_count

            first_page_index = excluded_leading_pages
            last_page_index = source_page_count - excluded_trailing_pages

            if first_page_index >= last_page_index:
                raise PdfParseError(
                    "The excluded leading and trailing pages would remove "
                    "the entire PDF."
                )

            retained_page_count = last_page_index - first_page_index

            page_lines: list[tuple[TextLine, ...]] = []

            for page_index in range(first_page_index, last_page_index):
                page = document.load_page(page_index)
                page_lines.append(tuple(_extract_page_lines(page)))

            lines = tuple(
                line
                for extracted_page_lines in page_lines
                for line in extracted_page_lines
            )

            pages = tuple(
                _lines_to_text(extracted_page_lines)
                for extracted_page_lines in page_lines
            )

            body_font_size = _estimate_body_font_size(lines)

            repeated_marginal_text = _find_repeated_marginal_text(
                lines,
                page_count=retained_page_count,
            )

            heading_lines = _find_heading_lines(
                lines,
                body_font_size=body_font_size,
                repeated_marginal_text=repeated_marginal_text,
            )

            heading_levels = _build_heading_level_map(heading_lines)

            sections = _build_sections(
                lines,
                heading_lines=heading_lines,
                heading_levels=heading_levels,
                page_count=retained_page_count,
            )

    except PdfParseError:
        raise
    except (
        pymupdf.FileDataError,
        pymupdf.FileNotFoundError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise PdfParseError(f"Could not parse PDF {path}: {exc}") from exc

    return ParsedPdf(
        source=path,
        source_page_count=source_page_count,
        page_count=retained_page_count,
        pages=pages,
        lines=lines,
        sections=sections,
        body_font_size=body_font_size,
    )


def _extract_page_lines(page: pymupdf.Page) -> list[TextLine]:
    """Extract and reconstruct visual text lines from a PDF page."""
    page_data: dict[str, Any] = page.get_text("dict", sort=False)
    fragments: list[TextLine] = []

    for block_number, block in enumerate(page_data.get("blocks", [])):
        if block.get("type") != 0:
            continue

        for line_number, line in enumerate(block.get("lines", [])):
            spans = line.get("spans", [])
            text = _join_span_text(spans)

            if not text:
                continue

            fragments.append(
                TextLine(
                    page_number=page.number + 1,
                    block_number=block_number,
                    line_number=line_number,
                    text=text,
                    font=_dominant_font(spans),
                    font_size=_dominant_font_size(spans),
                    is_bold=_line_is_bold(spans),
                    bbox=_normalise_bbox(line.get("bbox")),
                    page_height=float(page.rect.height),
                )
            )

    return _merge_visual_lines(fragments)

def _merge_visual_lines(
    fragments: Sequence[TextLine],
) -> list[TextLine]:
    """Merge text fragments that visually belong to the same line."""
    if not fragments:
        return []

    ordered = sorted(
        fragments,
        key=lambda item: (
            round(item.bbox[1], 1),
            item.bbox[0],
        ),
    )

    rows: list[list[TextLine]] = []

    for fragment in ordered:
        matching_row = next(
            (
                row
                for row in reversed(rows)
                if _same_visual_row(row[0], fragment)
            ),
            None,
        )

        if matching_row is None:
            rows.append([fragment])
        else:
            matching_row.append(fragment)

    merged_lines: list[TextLine] = []

    for row in rows:
        row.sort(key=lambda item: item.bbox[0])

        # This loop must be inside `for row in rows`.
        for group in _split_row_on_large_gaps(row):
            merged_line = _merge_fragment_group(
                group,
                line_number=len(merged_lines),
            )

            if merged_line.text:
                merged_lines.append(merged_line)

    return sorted(
        merged_lines,
        key=lambda item: (
            item.bbox[1],
            item.bbox[0],
        ),
    )


def _same_visual_row(
    left: TextLine,
    right: TextLine,
) -> bool:
    """Return whether two fragments occupy the same horizontal row."""
    left_y0, left_y1 = left.bbox[1], left.bbox[3]
    right_y0, right_y1 = right.bbox[1], right.bbox[3]

    overlap = min(left_y1, right_y1) - max(left_y0, right_y0)

    left_height = max(left_y1 - left_y0, 0.1)
    right_height = max(right_y1 - right_y0, 0.1)
    minimum_height = min(left_height, right_height)

    if overlap > 0:
        return overlap / minimum_height >= MIN_VERTICAL_OVERLAP_RATIO

    # Font bounding boxes can differ slightly even when baselines match.
    left_center = (left_y0 + left_y1) / 2
    right_center = (right_y0 + right_y1) / 2

    tolerance = max(left.font_size, right.font_size) * 0.25

    return abs(left_center - right_center) <= tolerance


def _split_row_on_large_gaps(
    row: Sequence[TextLine],
) -> list[list[TextLine]]:
    """Avoid combining separate columns that happen to share a row."""
    if not row:
        return []

    groups: list[list[TextLine]] = [[row[0]]]

    for fragment in row[1:]:
        previous = groups[-1][-1]
        horizontal_gap = fragment.bbox[0] - previous.bbox[2]

        maximum_gap = max(
            previous.font_size,
            fragment.font_size,
            1.0,
        ) * MAX_HORIZONTAL_GAP_FACTOR

        if horizontal_gap > maximum_gap:
            groups.append([fragment])
        else:
            groups[-1].append(fragment)

    return groups


def _merge_fragment_group(
    fragments: Sequence[TextLine],
    *,
    line_number: int,
) -> TextLine:
    """Combine adjacent visual fragments into one logical line."""
    text = _join_text_fragments(fragments)

    x0 = min(fragment.bbox[0] for fragment in fragments)
    y0 = min(fragment.bbox[1] for fragment in fragments)
    x1 = max(fragment.bbox[2] for fragment in fragments)
    y1 = max(fragment.bbox[3] for fragment in fragments)

    total_characters = sum(
        max(len(fragment.text), 1)
        for fragment in fragments
    )

    weighted_font_size = sum(
        fragment.font_size * max(len(fragment.text), 1)
        for fragment in fragments
    ) / total_characters

    bold_characters = sum(
        len(fragment.text)
        for fragment in fragments
        if fragment.is_bold
    )

    font_counts = Counter(
        {
            fragment.font: sum(
                len(item.text)
                for item in fragments
                if item.font == fragment.font
            )
            for fragment in fragments
        }
    )

    return TextLine(
        page_number=fragments[0].page_number,
        block_number=min(
            fragment.block_number
            for fragment in fragments
        ),
        line_number=line_number,
        text=text,
        font=font_counts.most_common(1)[0][0],
        font_size=round(weighted_font_size, 1),
        is_bold=bold_characters / total_characters >= 0.5,
        bbox=(x0, y0, x1, y1),
        page_height=fragments[0].page_height,
    )


def _join_text_fragments(
    fragments: Sequence[TextLine],
) -> str:
    """Join positioned fragments using normal textual spacing."""
    if not fragments:
        return ""

    result = fragments[0].text

    for previous, current in zip(
        fragments,
        fragments[1:],
        strict=False,
    ):
        if _should_insert_space(previous.text, current.text):
            result += " "

        result += current.text

    return _normalise_inline_text(result)


def _should_insert_space(
    previous: str,
    current: str,
) -> bool:
    """Determine whether adjacent fragments need a space."""
    no_space_before = ",.;:!?%)]}»"
    no_space_after = "([{«"

    if current.startswith(tuple(no_space_before)):
        return False

    if previous.endswith(tuple(no_space_after)):
        return False

    if previous.endswith(("-", "–", "—", "/", "'", "’")):
        return False

    return True


def _join_span_text(spans: Sequence[dict[str, Any]]) -> str:
    """Join all text spans belonging to the same visual line."""
    text = "".join(str(span.get("text", "")) for span in spans)
    return _normalise_inline_text(text)


def _remove_ignored_text(text: str) -> str:
    """Remove known unwanted text from extracted PDF content."""
    for pattern in IGNORED_TEXT_PATTERNS:
        text = pattern.sub("", text)

    return text


def _normalise_inline_text(text: str) -> str:
    """Remove unwanted content and normalize inline whitespace."""
    text = _remove_ignored_text(text)
    return re.sub(r"\s+", " ", text).strip()


def _normalise_bbox(
    bbox: Sequence[float] | None,
) -> tuple[float, float, float, float]:
    """Return a predictable four-coordinate bounding box."""
    if bbox is None or len(bbox) != 4:
        return (0.0, 0.0, 0.0, 0.0)

    return tuple(float(value) for value in bbox)  # type: ignore[return-value]


def _dominant_font(spans: Sequence[dict[str, Any]]) -> str:
    """Return the font used by the largest number of characters."""
    character_counts: Counter[str] = Counter()

    for span in spans:
        text = str(span.get("text", ""))
        font = str(span.get("font", ""))

        character_counts[font] += max(len(text.strip()), 1)

    if not character_counts:
        return ""

    return character_counts.most_common(1)[0][0]


def _dominant_font_size(spans: Sequence[dict[str, Any]]) -> float:
    """Return the font size used by the largest number of characters."""
    character_counts: Counter[float] = Counter()

    for span in spans:
        text = str(span.get("text", ""))
        size = round(float(span.get("size", 0.0)), 1)

        character_counts[size] += max(len(text.strip()), 1)

    if not character_counts:
        return 0.0

    return character_counts.most_common(1)[0][0]


def _line_is_bold(spans: Sequence[dict[str, Any]]) -> bool:
    """Return whether most visible characters on a line are bold."""
    bold_characters = 0
    total_characters = 0

    for span in spans:
        text = str(span.get("text", "")).strip()
        if not text:
            continue

        character_count = len(text)
        total_characters += character_count

        flags = int(span.get("flags", 0))
        font_name = str(span.get("font", ""))

        if _span_is_bold(flags, font_name):
            bold_characters += character_count

    if total_characters == 0:
        return False

    return bold_characters / total_characters >= 0.5


def _span_is_bold(flags: int, font_name: str) -> bool:
    """Detect bold text from flags with a font-name fallback."""
    if flags & pymupdf.TEXT_FONT_BOLD:
        return True

    normalised_font_name = re.sub(
        r"[^a-z]",
        "",
        font_name.casefold(),
    )

    bold_markers = (
        "bold",
        "semibold",
        "demibold",
        "heavy",
        "black",
        "extrabold",
    )

    return any(
        marker in normalised_font_name
        for marker in bold_markers
    )


def _lines_to_text(lines: Sequence[TextLine]) -> str:
    """Convert visual PDF lines into paragraph-oriented plain text."""
    return "\n\n".join(_lines_to_paragraphs(lines))


def _lines_to_paragraphs(
    lines: Sequence[TextLine],
) -> tuple[str, ...]:
    """Group visual lines into logical paragraphs."""
    if not lines:
        return ()

    paragraph_lines: list[list[TextLine]] = [[lines[0]]]

    for line in lines[1:]:
        previous = paragraph_lines[-1][-1]

        if _starts_new_paragraph(previous, line):
            paragraph_lines.append([line])
        else:
            paragraph_lines[-1].append(line)

    paragraphs = tuple(
        paragraph
        for group in paragraph_lines
        if (paragraph := _join_paragraph_lines(group))
    )

    return paragraphs


def _starts_new_paragraph(
    previous: TextLine,
    current: TextLine,
) -> bool:
    """Return whether *current* starts a new logical paragraph."""
    if current.page_number != previous.page_number:
        return True

    if current.block_number != previous.block_number:
        return True

    if current.font != previous.font:
        return True

    if abs(current.font_size - previous.font_size) >= 1.0:
        return True

    if current.is_bold != previous.is_bold:
        return True

    if re.match(r"^(?:[-*•]|\d+[.)])\s+", current.text):
        return True

    vertical_gap = current.bbox[1] - previous.bbox[3]
    expected_line_height = max(
        previous.bbox[3] - previous.bbox[1],
        current.bbox[3] - current.bbox[1],
        previous.font_size,
        current.font_size,
        1.0,
    )

    return vertical_gap > expected_line_height * 0.75


def _join_paragraph_lines(lines: Sequence[TextLine]) -> str:
    """Join wrapped visual lines into one normalized paragraph."""
    if not lines:
        return ""

    result = lines[0].text

    for line in lines[1:]:
        if result.endswith("-") and line.text[:1].islower():
            result = result[:-1] + line.text
        elif _should_insert_space(result, line.text):
            result += f" {line.text}"
        else:
            result += line.text

    return _normalise_inline_text(result)


def _estimate_body_font_size(
    lines: Iterable[TextLine],
) -> float | None:
    """Estimate body font size using character-weighted frequency."""
    size_counts: Counter[float] = Counter()

    for line in lines:
        if not line.text:
            continue

        size = round(line.font_size, 1)
        size_counts[size] += len(line.text)

    if not size_counts:
        return None

    return size_counts.most_common(1)[0][0]


def _find_repeated_marginal_text(
    lines: Sequence[TextLine],
    *,
    page_count: int,
) -> frozenset[str]:
    """Find repeated text near page tops or bottoms.

    Repeated marginal text is usually a running header, footer, or page label,
    rather than a chapter heading.
    """
    if page_count < 3:
        return frozenset()

    pages_by_text: defaultdict[str, set[int]] = defaultdict(set)

    for line in lines:
        if not _is_in_page_margin(line):
            continue

        normalised = _heading_key(line.text)
        if normalised:
            pages_by_text[normalised].add(line.page_number)

    minimum_pages = max(3, round(page_count * 0.25))

    return frozenset(
        text
        for text, page_numbers in pages_by_text.items()
        if len(page_numbers) >= minimum_pages
    )


def _is_in_page_margin(line: TextLine) -> bool:
    """Return whether the line is near the top or bottom of its page."""
    _, y0, _, y1 = line.bbox

    top_boundary = line.page_height * 0.10
    bottom_boundary = line.page_height * 0.90

    return y0 <= top_boundary or y1 >= bottom_boundary


def _find_heading_lines(
    lines: Sequence[TextLine],
    *,
    body_font_size: float | None,
    repeated_marginal_text: frozenset[str],
) -> tuple[TextLine, ...]:
    """Return lines likely to be headings."""
    if body_font_size is None or body_font_size <= 0:
        return ()

    return tuple(
        line
        for line in lines
        if _is_probable_heading(
            line,
            body_font_size=body_font_size,
            repeated_marginal_text=repeated_marginal_text,
        )
    )


def _is_probable_heading(
    line: TextLine,
    *,
    body_font_size: float,
    repeated_marginal_text: frozenset[str],
) -> bool:
    """Infer whether a line is a heading from typography and content."""
    text = line.text.strip()

    if not text:
        return False

    if _heading_key(text) in repeated_marginal_text:
        return False

    if not any(character.isalpha() for character in text):
        return False

    if len(text) > 120:
        return False

    word_count = len(text.split())
    if word_count > 16:
        return False

    # Avoid treating ordinary sentences as headings unless typography is
    # especially strong.
    ends_like_sentence = text.endswith((".", ";", "!", "?"))

    size_ratio = line.font_size / body_font_size

    significantly_larger = size_ratio >= 1.25
    moderately_larger_and_bold = (
        size_ratio >= 1.08
        and line.is_bold
    )
    body_sized_short_bold_heading = (
        size_ratio >= 0.98
        and line.is_bold
        and word_count <= 8
        and not ends_like_sentence
    )

    return (
        significantly_larger
        or moderately_larger_and_bold
        or body_sized_short_bold_heading
    )


def _heading_key(text: str) -> str:
    """Create a normalized key for heading comparisons."""
    return re.sub(
        r"\s+",
        " ",
        text.casefold(),
    ).strip()


def _build_heading_level_map(
    heading_lines: Sequence[TextLine],
) -> dict[float, int]:
    """Map heading font sizes to hierarchy levels.

    The largest detected size becomes level 1, the next becomes level 2,
    and all smaller heading sizes become level 3.
    """
    sizes = sorted(
        {
            round(line.font_size, 1)
            for line in heading_lines
        },
        reverse=True,
    )

    return {
        size: min(index + 1, 3)
        for index, size in enumerate(sizes)
    }


def _build_sections(
    lines: Sequence[TextLine],
    *,
    heading_lines: Sequence[TextLine],
    heading_levels: dict[float, int],
    page_count: int,
) -> tuple[ParsedSection, ...]:
    """Build sequential, Markdown-ready sections from inferred headings."""
    if not lines:
        return ()

    heading_ids = {
        _line_identity(line)
        for line in heading_lines
    }

    sections: list[ParsedSection] = []
    current_title: str | None = None
    current_level: int | None = None
    current_page_start = lines[0].page_number
    current_page_end = current_page_start
    current_body: list[TextLine] = []

    def flush_current_section() -> None:
        paragraphs = _lines_to_paragraphs(current_body)

        if current_title is None and not paragraphs:
            return

        sections.append(
            ParsedSection(
                title=current_title,
                level=current_level,
                page_start=current_page_start,
                page_end=current_page_end,
                paragraphs=paragraphs,
            )
        )

    for line in lines:
        identity = _line_identity(line)

        if identity in heading_ids:
            flush_current_section()

            current_title = line.text
            current_level = heading_levels.get(
                round(line.font_size, 1),
                3,
            )
            current_page_start = line.page_number
            current_page_end = line.page_number
            current_body = []
            continue

        current_body.append(line)
        current_page_end = line.page_number

    flush_current_section()

    if sections:
        return tuple(sections)

    # Fallback for documents where no headings were detected.
    return (
        ParsedSection(
            title=None,
            level=None,
            page_start=lines[0].page_number,
            page_end=lines[-1].page_number if lines else page_count,
            paragraphs=_lines_to_paragraphs(lines),
        ),
    )


def _line_identity(
    line: TextLine,
) -> tuple[int, int, int]:
    """Return a stable identity for an extracted line."""
    return (
        line.page_number,
        line.block_number,
        line.line_number,
    )


def _normalise_page_text(text: str) -> str:
    """Remove unwanted content and normalize page whitespace."""
    text = _remove_ignored_text(text)

    normalized_lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.splitlines()
    ]

    return "\n".join(
        line
        for line in normalized_lines
        if line
    ).strip()
