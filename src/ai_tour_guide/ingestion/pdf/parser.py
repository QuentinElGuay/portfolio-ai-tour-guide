"""Core PDF download and structured parsing logic."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, fields
from datetime import date
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
import unicodedata
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import pymupdf

TMP_FOLDER = Path('tmp')
OUTPUT_SUFFIXES = {'.pdf', '.md', '.txt', '.json'}

MIN_SECTION_HEADING_SIZE_RATIO = 1.25
PAGE_TITLE_SIZE_RATIO = 1.50
CHAPTER_TITLE_SIZE_RATIO = 1.70
MIN_SUBSECTION_SIZE_RATIO = 1.06
MIN_SUBSECTION_FONT_SIZE_DELTA = 0.5
PAGE_TITLE_MAX_Y_RATIO = 0.35
CHAPTER_PAGE_MAX_BODY_CHARACTERS = 180

MAX_HORIZONTAL_GAP_FACTOR = 3.0
MIN_VERTICAL_OVERLAP_RATIO = 0.6

DEFAULT_DOWNLOAD_DIRECTORY = Path('.cache/pdf-ingestion')


class PdfDownloadError(RuntimeError):
    """Raised when a PDF cannot be downloaded or validated."""


class PdfParseError(RuntimeError):
    """Raised when a downloaded file cannot be parsed as a PDF."""


@dataclass(frozen=True, slots=True)
class IngestionDocument:
    """Input document accepted by the ingestion pipeline.

    Add new document-level metadata here as the ingestion format evolves.
    """

    title: str
    pdf_url: str
    excluded_leading_pages: int = 3
    excluded_trailing_pages: int = 2
    authors: list[str] | None = None
    keywords: list[str] | None = None
    publisher: str | None = None
    publication_date: date | None = None
    ignored_text_patterns: tuple[re.Pattern[str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.title, str):
            raise ValueError('title must be a string')
        if not self.title.strip():
            raise ValueError('title must not be empty')

        normalize_filename_stem(self.title)

        parsed_url = urlparse(self.pdf_url)
        if parsed_url.scheme not in {'http', 'https'} or not parsed_url.netloc:
            raise ValueError('pdf_url must be a valid HTTP or HTTPS URL')

        if self.excluded_leading_pages < 0:
            raise ValueError(
                'excluded_leading_pages must be greater than or equal to 0'
            )
        if self.excluded_trailing_pages < 0:
            raise ValueError(
                'excluded_trailing_pages must be greater than or equal to 0'
            )

        _validate_optional_string_list(self.authors, field_name='authors')
        _validate_optional_string_list(self.keywords, field_name='keywords')

    @property
    def filename_stem(self) -> str:
        """Return the normalized stem used by downloaded and generated files."""
        return normalize_filename_stem(self.title)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> IngestionDocument:
        """Build and validate a document from its JSON representation."""
        accepted_fields = {field.name for field in fields(cls)}
        unknown_fields = sorted(set(values) - accepted_fields)
        if unknown_fields:
            raise ValueError('Unknown document field(s): ' + ', '.join(unknown_fields))

        normalized = dict(values)

        publication_date = normalized.get('publication_date')
        if publication_date is not None:
            if not isinstance(publication_date, str):
                raise ValueError('publication_date must be an ISO-8601 date string')
            try:
                normalized['publication_date'] = date.fromisoformat(publication_date)
            except ValueError as exc:
                raise ValueError(
                    'publication_date must use the YYYY-MM-DD format'
                ) from exc

        ignored_patterns = normalized.get('ignored_text_patterns')

        if ignored_patterns is not None:
            if not isinstance(ignored_patterns, list) or not all(
                isinstance(pattern, str) for pattern in ignored_patterns
            ):
                raise ValueError('ignored_text_patterns must be an array of strings')

            compiled_patterns: list[re.Pattern[str]] = []

            for index, pattern in enumerate(ignored_patterns, start=1):
                try:
                    compiled_patterns.append(re.compile(pattern, flags=re.IGNORECASE))
                except re.error as exc:
                    raise ValueError(
                        f'Invalid ignored_text_patterns regex '
                        f'at position {index}: {exc}'
                    ) from exc

            normalized['ignored_text_patterns'] = tuple(compiled_patterns)

        try:
            return cls(**normalized)
        except TypeError as exc:
            raise ValueError(f'Invalid ingestion document: {exc}') from exc


def _validate_optional_string_list(
    value: list[str] | None,
    *,
    field_name: str,
) -> None:
    """Validate an optional list of non-empty strings."""
    if value is None:
        return

    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f'{field_name} must be an array of non-empty strings')


def normalize_filename_stem(title: str) -> str:
    """Convert a document title into a safe, extension-free filename stem."""
    candidate = title.strip()
    suffix = Path(candidate).suffix.lower()
    if suffix in OUTPUT_SUFFIXES:
        candidate = candidate[: -len(suffix)]

    candidate = unicodedata.normalize('NFKD', candidate)
    candidate = candidate.encode('ascii', 'ignore').decode('ascii')
    candidate = re.sub(r'[^A-Za-z0-9]+', '-', candidate)
    candidate = candidate.strip('-').lower()

    if not candidate:
        raise ValueError(
            'title must contain at least one letter or number that can be used '
            'in a filename'
        )

    return candidate


class IngestionSettings(BaseSettings):
    """Operational configuration for PDF ingestion."""

    model_config = SettingsConfigDict(
        env_prefix='INGESTION_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    tmp_folder: Path = TMP_FOLDER
    timeout: float = Field(default=30.0, gt=0)
    verbose: bool = False


@dataclass(frozen=True, slots=True)
class _TextLine:
    """Internal typography-aware representation of one visual PDF line.

    This type is intentionally private. Coordinates and font information are
    needed while reconstructing paragraphs and detecting headings, but they are
    extraction details rather than part of the parser's public domain model.
    """

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
class ParsedParagraph:
    """One page-aware paragraph extracted from the PDF."""

    text: str
    page_start: int
    page_end: int

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible paragraph data."""
        return {
            'text': self.text,
            'page_start': self.page_start,
            'page_end': self.page_end,
        }


@dataclass(frozen=True, slots=True)
class ParsedSection:
    """A hierarchical section inferred from PDF typography."""

    title: str | None
    level: int | None
    page_start: int
    page_end: int
    paragraphs: tuple[ParsedParagraph, ...]
    subsections: tuple[ParsedSection, ...] = ()

    @property
    def text(self) -> str:
        """Return only paragraphs directly attached to this section."""
        return '\n\n'.join(paragraph.text for paragraph in self.paragraphs)

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible section data, including descendants."""
        return {
            'title': self.title,
            'level': self.level,
            'page_start': self.page_start,
            'page_end': self.page_end,
            'paragraphs': [paragraph.to_dict() for paragraph in self.paragraphs],
            'subsections': [subsection.to_dict() for subsection in self.subsections],
        }

    def iter_sections(self) -> Iterable[ParsedSection]:
        """Yield this section and all descendants in document order."""
        yield self

        for subsection in self.subsections:
            yield from subsection.iter_sections()


@dataclass(frozen=True, slots=True)
class ParsedPdfMetadata:
    """Resolved metadata attached to a parsed ingestion document.

    Explicit values from :class:`IngestionDocument` take precedence. Missing
    values are populated from the PDF metadata when possible.
    """

    title: str | None
    pdf_url: str
    publisher: str | None
    publication_date: date | None
    authors: list[str]
    subject: str | None
    keywords: list[str]
    creator: str | None
    producer: str | None
    pdf_format: str | None
    creation_date: str | None
    modification_date: str | None
    source_page_count: int
    page_count: int

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible resolved metadata."""
        return {
            'title': self.title,
            'pdf_url': self.pdf_url,
            'publisher': self.publisher,
            'publication_date': (
                self.publication_date.isoformat()
                if self.publication_date is not None
                else None
            ),
            'authors': list(self.authors),
            'subject': self.subject,
            'keywords': list(self.keywords),
            'creator': self.creator,
            'producer': self.producer,
            'format': self.pdf_format,
            'creation_date': self.creation_date,
            'modification_date': self.modification_date,
            'source_page_count': self.source_page_count,
            'page_count': self.page_count,
        }


@dataclass(frozen=True, slots=True)
class ParsedPdf:
    """Canonical structured result returned by :func:`parse_pdf`.

    Page-level text and typography diagnostics stay internal. The public model
    contains resolved metadata plus section and paragraph structures used by
    Markdown visualization and downstream RAG chunking.
    """

    metadata: ParsedPdfMetadata
    sections: tuple[ParsedSection, ...]

    @property
    def title(self) -> str | None:
        """Return the resolved document title."""
        return self.metadata.title

    @property
    def text(self) -> str:
        """Return all retained paragraph text in document order."""
        paragraphs = (
            paragraph.text
            for root_section in self.sections
            for section in root_section.iter_sections()
            for paragraph in section.paragraphs
            if paragraph.text
        )

        return '\n\n'.join(paragraphs)

    def to_dict(self) -> dict[str, object]:
        """Return the parsed document as JSON-compatible data."""
        return {
            'metadata': self.metadata.to_dict(),
            'sections': [section.to_dict() for section in self.sections],
        }

    def to_json(
        self,
        *,
        indent: int | None = 2,
        ensure_ascii: bool = False,
    ) -> str:
        """Serialize the parsed document as JSON."""
        return json.dumps(
            self.to_dict(),
            ensure_ascii=ensure_ascii,
            indent=indent,
        )

    def write_json(
        self,
        destination: Path,
        *,
        indent: int | None = 2,
        ensure_ascii: bool = False,
    ) -> Path:
        """Write the parsed document to a UTF-8 JSON file."""
        destination = destination.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            self.to_json(indent=indent, ensure_ascii=ensure_ascii) + '\n',
            encoding='utf-8',
        )
        return destination


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
        headers={'User-Agent': 'portfolio-ai-tour-guide/0.1'},
    )

    temp_path: Path | None = None

    try:
        with http_client.stream('GET', url) as response:
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            if content_type and 'pdf' not in content_type:
                raise PdfDownloadError(
                    f'Expected a PDF response, received {content_type!r}.'
                )

            with NamedTemporaryFile(
                mode='wb',
                delete=False,
                dir=destination.parent,
                suffix='.part',
            ) as temp_file:
                temp_path = Path(temp_file.name)

                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    temp_file.write(chunk)

        if temp_path.stat().st_size == 0:
            raise PdfDownloadError('The downloaded file is empty.')

        with temp_path.open('rb') as file_handle:
            if file_handle.read(5) != b'%PDF-':
                raise PdfDownloadError('The downloaded file is not a valid PDF.')

        temp_path.replace(destination)
        return destination

    except (httpx.HTTPError, OSError) as exc:
        raise PdfDownloadError(f'Could not download PDF from {url}: {exc}') from exc

    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

        if owns_client:
            http_client.close()


def parse_pdf(
    document: IngestionDocument,
    *,
    download_directory: Path = DEFAULT_DOWNLOAD_DIRECTORY,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> ParsedPdf:
    """Download and parse an ingestion document.

    ``IngestionDocument`` supplies explicit metadata overrides, page
    exclusions, and ignored-text rules. Missing metadata is populated from the
    PDF metadata when available.
    """
    _validate_ingestion_document(document)

    destination = _build_pdf_destination(
        document,
        download_directory=download_directory,
    )
    downloaded_path = download_pdf(
        document.pdf_url,
        destination,
        timeout_seconds=timeout_seconds,
        client=client,
    )

    return _parse_downloaded_pdf(downloaded_path, document=document)


def _validate_ingestion_document(document: IngestionDocument) -> None:
    """Validate ingestion metadata and parser configuration."""
    if not document.pdf_url.strip():
        raise ValueError('document.pdf_url cannot be empty')

    if document.excluded_leading_pages < 0:
        raise ValueError('document.excluded_leading_pages cannot be negative')

    if document.excluded_trailing_pages < 0:
        raise ValueError('document.excluded_trailing_pages cannot be negative')

    for pattern in document.ignored_text_patterns:
        if not isinstance(pattern, re.Pattern):
            raise TypeError(
                'document.ignored_text_patterns must contain compiled regex patterns'
            )


def _build_pdf_destination(
    document: IngestionDocument,
    *,
    download_directory: Path,
) -> Path:
    """Build a stable, collision-resistant local destination for a PDF."""
    download_directory = download_directory.expanduser().resolve()
    download_directory.mkdir(parents=True, exist_ok=True)

    title_for_filename = _clean_optional_text(document.title) or 'document'
    safe_title = re.sub(r'[^\w.-]+', '-', title_for_filename, flags=re.UNICODE)
    safe_title = safe_title.strip('-_.')[:80] or 'document'
    url_digest = sha256(document.pdf_url.encode('utf-8')).hexdigest()[:12]

    return download_directory / f'{safe_title}-{url_digest}.pdf'


def _parse_downloaded_pdf(
    path: Path,
    *,
    document: IngestionDocument,
) -> ParsedPdf:
    """Parse a downloaded PDF using its ingestion configuration."""
    path = path.expanduser().resolve()

    if not path.is_file():
        raise PdfParseError(f'PDF file does not exist: {path}')

    try:
        with pymupdf.open(path) as pdf:
            if pdf.needs_pass and pdf.authenticate('') <= 0:
                raise PdfParseError('The PDF is encrypted and cannot be opened.')

            source_page_count = pdf.page_count
            first_page_index = document.excluded_leading_pages
            last_page_index = (
                source_page_count - document.excluded_trailing_pages
            )

            if first_page_index >= last_page_index:
                raise PdfParseError(
                    'The excluded leading and trailing pages would remove '
                    'the entire PDF.'
                )

            retained_page_count = last_page_index - first_page_index
            raw_lines = tuple(
                line
                for page_index in range(first_page_index, last_page_index)
                for line in _extract_page_lines(
                    pdf.load_page(page_index),
                    document=document,
                )
            )

            repeated_marginal_text = _find_repeated_marginal_text(
                raw_lines,
                page_count=retained_page_count,
            )
            lines = tuple(
                line
                for line in raw_lines
                if not _is_repeated_marginal_line(
                    line,
                    repeated_marginal_text,
                )
            )

            body_font_size = _estimate_body_font_size(lines)
            heading_lines = _find_heading_lines(
                lines,
                body_font_size=body_font_size,
            )
            heading_levels = _build_heading_level_map(
                lines,
                heading_lines,
                body_font_size=body_font_size,
            )
            flat_sections = _build_sections(
                lines,
                heading_lines=heading_lines,
                heading_levels=heading_levels,
                document=document,
            )

            sections = _nest_sections(flat_sections)
            pdf_metadata = _normalise_metadata(pdf.metadata)
            xmp_authors = _extract_xmp_authors(pdf)
            metadata = _resolve_pdf_metadata(
                document,
                pdf_metadata=pdf_metadata,
                xmp_authors=xmp_authors,
                source_page_count=source_page_count,
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
        raise PdfParseError(f'Could not parse PDF {path}: {exc}') from exc

    return ParsedPdf(
        metadata=metadata,
        sections=sections,
    )


def _extract_page_lines(
    page: pymupdf.Page,
    *,
    document: IngestionDocument,
) -> list[_TextLine]:
    """Extract and reconstruct visual text lines from one PDF page."""
    page_data: dict[str, Any] = page.get_text('dict', sort=False)
    fragments: list[_TextLine] = []

    for block_number, block in enumerate(page_data.get('blocks', [])):
        if block.get('type') != 0:
            continue

        for line_number, line in enumerate(block.get('lines', [])):
            spans = line.get('spans', [])
            text = _join_span_text(spans, document=document)

            if not text:
                continue

            fragments.append(
                _TextLine(
                    page_number=page.number + 1,
                    block_number=block_number,
                    line_number=line_number,
                    text=text,
                    font=_dominant_font(spans),
                    font_size=_dominant_font_size(spans),
                    is_bold=_line_is_bold(spans),
                    bbox=_normalise_bbox(line.get('bbox')),
                    page_height=float(page.rect.height),
                )
            )

    return _merge_visual_lines(fragments, document=document)


def _merge_visual_lines(
    fragments: Sequence[_TextLine],
    *,
    document: IngestionDocument,
) -> list[_TextLine]:
    """Merge positioned fragments that visually belong to the same row."""
    if not fragments:
        return []

    ordered = sorted(
        fragments,
        key=lambda item: (
            round(item.bbox[1], 1),
            item.bbox[0],
        ),
    )
    rows: list[list[_TextLine]] = []

    for fragment in ordered:
        matching_row = next(
            (row for row in reversed(rows) if _same_visual_row(row[0], fragment)),
            None,
        )

        if matching_row is None:
            rows.append([fragment])
        else:
            matching_row.append(fragment)

    merged_lines: list[_TextLine] = []

    for row in rows:
        row.sort(key=lambda item: item.bbox[0])

        for group in _split_row_on_large_gaps(row):
            merged_line = _merge_fragment_group(
                group,
                line_number=len(merged_lines),
                document=document,
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


def _same_visual_row(left: _TextLine, right: _TextLine) -> bool:
    """Return whether two fragments occupy the same horizontal row."""
    left_y0, left_y1 = left.bbox[1], left.bbox[3]
    right_y0, right_y1 = right.bbox[1], right.bbox[3]
    overlap = min(left_y1, right_y1) - max(left_y0, right_y0)
    left_height = max(left_y1 - left_y0, 0.1)
    right_height = max(right_y1 - right_y0, 0.1)
    minimum_height = min(left_height, right_height)

    if overlap > 0:
        return overlap / minimum_height >= MIN_VERTICAL_OVERLAP_RATIO

    left_center = (left_y0 + left_y1) / 2
    right_center = (right_y0 + right_y1) / 2
    tolerance = max(left.font_size, right.font_size) * 0.25

    return abs(left_center - right_center) <= tolerance


def _split_row_on_large_gaps(
    row: Sequence[_TextLine],
) -> list[list[_TextLine]]:
    """Avoid combining separate columns that happen to share a row."""
    if not row:
        return []

    groups: list[list[_TextLine]] = [[row[0]]]

    for fragment in row[1:]:
        previous = groups[-1][-1]
        horizontal_gap = fragment.bbox[0] - previous.bbox[2]
        maximum_gap = (
            max(previous.font_size, fragment.font_size, 1.0)
            * MAX_HORIZONTAL_GAP_FACTOR
        )

        if horizontal_gap > maximum_gap:
            groups.append([fragment])
        else:
            groups[-1].append(fragment)

    return groups


def _merge_fragment_group(
    fragments: Sequence[_TextLine],
    *,
    line_number: int,
    document: IngestionDocument,
) -> _TextLine:
    """Combine adjacent visual fragments into one internal line."""
    text = _join_text_fragments(fragments, document=document)
    x0 = min(fragment.bbox[0] for fragment in fragments)
    y0 = min(fragment.bbox[1] for fragment in fragments)
    x1 = max(fragment.bbox[2] for fragment in fragments)
    y1 = max(fragment.bbox[3] for fragment in fragments)
    total_characters = sum(max(len(fragment.text), 1) for fragment in fragments)
    weighted_font_size = (
        sum(
            fragment.font_size * max(len(fragment.text), 1)
            for fragment in fragments
        )
        / total_characters
    )
    bold_characters = sum(
        len(fragment.text) for fragment in fragments if fragment.is_bold
    )
    font_counts = Counter(
        {
            fragment.font: sum(
                len(item.text) for item in fragments if item.font == fragment.font
            )
            for fragment in fragments
        }
    )

    return _TextLine(
        page_number=fragments[0].page_number,
        block_number=min(fragment.block_number for fragment in fragments),
        line_number=line_number,
        text=text,
        font=font_counts.most_common(1)[0][0],
        font_size=round(weighted_font_size, 1),
        is_bold=bold_characters / total_characters >= 0.5,
        bbox=(x0, y0, x1, y1),
        page_height=fragments[0].page_height,
    )


def _join_text_fragments(
    fragments: Sequence[_TextLine],
    *,
    document: IngestionDocument,
) -> str:
    """Join positioned fragments using normal textual spacing."""
    if not fragments:
        return ''

    result = fragments[0].text

    for previous, current in zip(fragments, fragments[1:], strict=False):
        if _should_insert_space(previous.text, current.text):
            result += ' '
        result += current.text

    return _normalise_inline_text(result, document=document)


def _should_insert_space(previous: str, current: str) -> bool:
    """Determine whether adjacent text fragments need a space."""
    no_space_before = ',.;:!?%)]}»'
    no_space_after = '([{«'

    if current.startswith(tuple(no_space_before)):
        return False
    if previous.endswith(tuple(no_space_after)):
        return False
    if previous.endswith(('-', '–', '—', '/', "'", '’')):
        return False

    return True


def _join_span_text(
    spans: Sequence[dict[str, Any]],
    *,
    document: IngestionDocument,
) -> str:
    """Join all text spans belonging to the same visual line."""
    text = ''.join(str(span.get('text', '')) for span in spans)
    return _normalise_inline_text(text, document=document)


def _remove_ignored_text(text: str, *, document: IngestionDocument) -> str:
    """Remove text matched by the ingestion document's ignore rules."""
    for pattern in document.ignored_text_patterns:
        text = pattern.sub('', text)

    return text


def _normalise_inline_text(
    text: str,
    *,
    document: IngestionDocument,
) -> str:
    """Remove unwanted content and normalize inline whitespace."""
    text = _remove_ignored_text(text, document=document)
    return re.sub(r'\s+', ' ', text).strip()


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
        text = str(span.get('text', ''))
        font = str(span.get('font', ''))
        character_counts[font] += max(len(text.strip()), 1)

    return character_counts.most_common(1)[0][0] if character_counts else ''


def _dominant_font_size(spans: Sequence[dict[str, Any]]) -> float:
    """Return the font size used by the largest number of characters."""
    character_counts: Counter[float] = Counter()

    for span in spans:
        text = str(span.get('text', ''))
        size = round(float(span.get('size', 0.0)), 1)
        character_counts[size] += max(len(text.strip()), 1)

    return character_counts.most_common(1)[0][0] if character_counts else 0.0


def _line_is_bold(spans: Sequence[dict[str, Any]]) -> bool:
    """Return whether most visible characters on a line are bold."""
    bold_characters = 0
    total_characters = 0

    for span in spans:
        text = str(span.get('text', '')).strip()
        if not text:
            continue

        character_count = len(text)
        total_characters += character_count
        flags = int(span.get('flags', 0))
        font_name = str(span.get('font', ''))

        if _span_is_bold(flags, font_name):
            bold_characters += character_count

    return total_characters > 0 and bold_characters / total_characters >= 0.5


def _span_is_bold(flags: int, font_name: str) -> bool:
    """Detect bold text from flags with a font-name fallback."""
    if flags & pymupdf.TEXT_FONT_BOLD:
        return True

    normalised_font_name = re.sub(r'[^a-z]', '', font_name.casefold())
    bold_markers = (
        'bold',
        'semibold',
        'demibold',
        'heavy',
        'black',
        'extrabold',
    )

    return any(marker in normalised_font_name for marker in bold_markers)


def _lines_to_paragraphs(
    lines: Sequence[_TextLine],
    *,
    document: IngestionDocument,
) -> tuple[ParsedParagraph, ...]:
    """Group internal visual lines into logical, page-aware paragraphs."""
    if not lines:
        return ()

    paragraph_lines: list[list[_TextLine]] = [[lines[0]]]

    for line in lines[1:]:
        previous = paragraph_lines[-1][-1]

        if _starts_new_paragraph(previous, line):
            paragraph_lines.append([line])
        else:
            paragraph_lines[-1].append(line)

    return tuple(
        ParsedParagraph(
            text=text,
            page_start=min(line.page_number for line in group),
            page_end=max(line.page_number for line in group),
        )
        for group in paragraph_lines
        if (text := _join_paragraph_lines(group, document=document))
    )


def _starts_new_paragraph(previous: _TextLine, current: _TextLine) -> bool:
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
    if re.match(r'^(?:[-*•]|\d+[.)])\s+', current.text):
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


def _join_paragraph_lines(
    lines: Sequence[_TextLine],
    *,
    document: IngestionDocument,
) -> str:
    """Join wrapped visual lines into one normalized paragraph."""
    if not lines:
        return ''

    result = lines[0].text

    for line in lines[1:]:
        if result.endswith('-') and line.text[:1].islower():
            result = result[:-1] + line.text
        elif _should_insert_space(result, line.text):
            result += f' {line.text}'
        else:
            result += line.text

    return _normalise_inline_text(result, document=document)


def _estimate_body_font_size(lines: Iterable[_TextLine]) -> float | None:
    """Estimate body font size using character-weighted frequency."""
    size_counts: Counter[float] = Counter()

    for line in lines:
        if line.text:
            size_counts[round(line.font_size, 1)] += len(line.text)

    return size_counts.most_common(1)[0][0] if size_counts else None


def _find_repeated_marginal_text(
    lines: Sequence[_TextLine],
    *,
    page_count: int,
) -> frozenset[str]:
    """Find repeated text near page tops or bottoms."""
    if page_count < 3:
        return frozenset()

    pages_by_text: defaultdict[str, set[int]] = defaultdict(set)

    for line in lines:
        if _is_in_page_margin(line):
            normalised = _heading_key(line.text)
            if normalised:
                pages_by_text[normalised].add(line.page_number)

    minimum_pages = max(3, round(page_count * 0.25))

    return frozenset(
        text
        for text, page_numbers in pages_by_text.items()
        if len(page_numbers) >= minimum_pages
    )


def _is_repeated_marginal_line(
    line: _TextLine,
    repeated_marginal_text: frozenset[str],
) -> bool:
    """Return whether a line is a detected running header or footer."""
    return (
        _is_in_page_margin(line) and _heading_key(line.text) in repeated_marginal_text
    )


def _is_in_page_margin(line: _TextLine) -> bool:
    """Return whether the line is near the top or bottom of its page."""
    _, y0, _, y1 = line.bbox
    top_boundary = line.page_height * 0.10
    bottom_boundary = line.page_height * 0.90

    return y0 <= top_boundary or y1 >= bottom_boundary


def _find_heading_lines(
    lines: Sequence[_TextLine],
    *,
    body_font_size: float | None,
) -> tuple[_TextLine, ...]:
    """Return lines likely to be headings."""
    if body_font_size is None or body_font_size <= 0:
        return ()

    return tuple(
        line
        for line in lines
        if _is_probable_heading(line, body_font_size=body_font_size)
    )


def _is_probable_heading(
    line: _TextLine,
    *,
    body_font_size: float,
) -> bool:
    """Infer whether a line is a heading from typography and content."""
    text = line.text.strip()

    if not text:
        return False

    if not any(character.isalpha() for character in text):
        return False

    if len(text) > 120:
        return False

    word_count = len(text.split())

    if word_count > 16:
        return False

    ends_like_sentence = text.endswith(('.', ';', '!', '?'))
    size_ratio = line.font_size / body_font_size

    significantly_larger = size_ratio >= MIN_SECTION_HEADING_SIZE_RATIO
    moderately_larger_and_bold = size_ratio >= 1.08 and line.is_bold
    body_sized_short_bold_heading = (
        size_ratio >= 0.98
        and line.is_bold
        and word_count <= 10
        and not ends_like_sentence
    )

    return (
        significantly_larger
        or moderately_larger_and_bold
        or body_sized_short_bold_heading
    )


def _heading_key(text: str) -> str:
    """Create a normalized key for heading comparisons."""
    return re.sub(r'\s+', ' ', text.casefold()).strip()


def _build_heading_level_map(
    lines: Sequence[_TextLine],
    heading_lines: Sequence[_TextLine],
    *,
    body_font_size: float | None,
) -> dict[tuple[int, int, int], int]:
    """Assign heading levels using page layout and relative font size."""
    if body_font_size is None or body_font_size <= 0:
        return {}

    heading_ids = {_line_identity(line) for line in heading_lines}
    body_characters_by_page: Counter[int] = Counter()

    for line in lines:
        if _line_identity(line) not in heading_ids:
            body_characters_by_page[line.page_number] += len(line.text)

    levels: dict[tuple[int, int, int], int] = {}

    for line in heading_lines:
        identity = _line_identity(line)
        size_ratio = line.font_size / body_font_size

        page_body_characters = body_characters_by_page[line.page_number]
        is_sparse_chapter_page = (
            page_body_characters <= CHAPTER_PAGE_MAX_BODY_CHARACTERS
        )
        is_near_page_top = (
            line.bbox[1] <= line.page_height * PAGE_TITLE_MAX_Y_RATIO
        )

        if size_ratio >= CHAPTER_TITLE_SIZE_RATIO and is_sparse_chapter_page:
            level = 1
        elif size_ratio >= PAGE_TITLE_SIZE_RATIO and is_near_page_top:
            level = 2
        else:
            level = 3

        levels[identity] = level

    return levels


def _is_heading_continuation(
    previous: _TextLine,
    current: _TextLine,
    *,
    previous_level: int | None,
    current_level: int,
    combined_title: str,
) -> bool:
    """Return whether two detected headings form one multiline title."""
    if previous.page_number != current.page_number:
        return False

    if previous_level != current_level:
        return False

    if previous.font != current.font:
        return False

    if previous.is_bold != current.is_bold:
        return False

    if abs(previous.font_size - current.font_size) > 0.5:
        return False

    if previous.text.endswith(('.', ';', '!', '?')):
        return False

    if len(combined_title.split()) > 20:
        return False

    vertical_gap = current.bbox[1] - previous.bbox[3]
    line_height = max(
        previous.bbox[3] - previous.bbox[1],
        current.bbox[3] - current.bbox[1],
        previous.font_size,
        current.font_size,
        1.0,
    )

    return -line_height * 0.25 <= vertical_gap <= line_height * 1.5


def _join_heading_lines(previous: str, current: str) -> str:
    """Join consecutive visual lines belonging to one heading."""
    if previous.endswith('-') and current[:1].islower():
        return previous[:-1] + current

    return f'{previous} {current}'.strip()


def _build_sections(
    lines: Sequence[_TextLine],
    *,
    heading_lines: Sequence[_TextLine],
    heading_levels: dict[tuple[int, int, int], int],
    document: IngestionDocument,
) -> tuple[ParsedSection, ...]:
    """Build sections while merging multiline visual headings."""
    if not lines:
        return ()

    heading_ids = {_line_identity(line) for line in heading_lines}
    sections: list[ParsedSection] = []

    current_title: str | None = None
    current_level: int | None = None
    current_heading_line: _TextLine | None = None

    current_page_start = lines[0].page_number
    current_page_end = current_page_start
    current_body: list[_TextLine] = []

    def flush_current_section() -> None:
        paragraphs = _lines_to_paragraphs(current_body, document=document)

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
            candidate_level = heading_levels.get(identity, 3)
            combined_title = _join_heading_lines(
                current_title or '',
                line.text,
            )

            if (
                current_title is not None
                and not current_body
                and current_heading_line is not None
                and _is_heading_continuation(
                    current_heading_line,
                    line,
                    previous_level=current_level,
                    current_level=candidate_level,
                    combined_title=combined_title,
                )
            ):
                current_title = combined_title
                current_page_end = line.page_number
                current_heading_line = line
                continue

            flush_current_section()

            current_title = line.text
            current_level = candidate_level
            current_heading_line = line
            current_page_start = line.page_number
            current_page_end = line.page_number
            current_body = []
            continue

        current_body.append(line)
        current_page_end = line.page_number

    flush_current_section()

    if sections:
        return tuple(sections)

    return (
        ParsedSection(
            title=None,
            level=None,
            page_start=lines[0].page_number,
            page_end=lines[-1].page_number,
            paragraphs=_lines_to_paragraphs(lines, document=document),
        ),
    )


def _line_identity(line: _TextLine) -> tuple[int, int, int]:
    """Return a stable identity for an internal extracted line."""
    return (
        line.page_number,
        line.block_number,
        line.line_number,
    )


def _resolve_pdf_metadata(
    document: IngestionDocument,
    *,
    pdf_metadata: dict[str, str],
    xmp_authors: Sequence[str],
    source_page_count: int,
    page_count: int,
) -> ParsedPdfMetadata:
    """Merge ingestion overrides with metadata extracted from the PDF.

    Author precedence is: explicit ingestion authors, XMP ``dc:creator``,
    then the legacy PDF ``Author`` information field.
    """
    embedded_title = _metadata_value(pdf_metadata, 'Title')
    embedded_publisher = _metadata_value(pdf_metadata, 'Publisher')
    embedded_creation_date = _metadata_value(
        pdf_metadata,
        'Creationdate',
    )
    ingestion_authors = _normalise_authors(document.authors)
    xmp_resolved_authors = _normalise_authors(xmp_authors)
    legacy_authors = _parse_legacy_authors(
        _metadata_value(pdf_metadata, 'Author')
    )
    ingestion_keywords = _normalise_keywords(document.keywords)
    embedded_keywords = _normalise_keywords(
        _metadata_value(pdf_metadata, 'Keywords')
    )

    return ParsedPdfMetadata(
        title=_clean_optional_text(document.title) or embedded_title,
        pdf_url=document.pdf_url.strip(),
        publisher=(
            _clean_optional_text(document.publisher)
            or embedded_publisher
        ),
        publication_date=(
            document.publication_date
            or _parse_pdf_metadata_date(embedded_creation_date)
        ),
        authors=(
            ingestion_authors
            or xmp_resolved_authors
            or legacy_authors
        ),
        subject=_metadata_value(pdf_metadata, 'Subject'),
        keywords=ingestion_keywords or embedded_keywords,
        creator=_metadata_value(pdf_metadata, 'Creator'),
        producer=_metadata_value(pdf_metadata, 'Producer'),
        pdf_format=_metadata_value(pdf_metadata, 'Format'),
        creation_date=embedded_creation_date,
        modification_date=_metadata_value(pdf_metadata, 'Moddate'),
        source_page_count=source_page_count,
        page_count=page_count,
    )


def _extract_xmp_authors(pdf: pymupdf.Document) -> list[str]:
    """Extract ordered authors from the XMP ``dc:creator`` sequence.

    Malformed or unavailable XMP metadata is ignored so the parser can fall
    back to the legacy document-information ``Author`` field.
    """
    try:
        xref_method = getattr(pdf, 'xref_xml_metadata', None)
        if xref_method is None:
            xref_method = getattr(pdf, 'xml_metadata_xref', None)
        if xref_method is None:
            return []

        metadata_xref = int(xref_method())
        if metadata_xref <= 0:
            return []

        xml_data = pdf.xref_stream(metadata_xref)
        if not xml_data:
            return []

        root = ElementTree.fromstring(xml_data)
    except (
        AttributeError,
        ElementTree.ParseError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return []

    dc_namespace = 'http://purl.org/dc/elements/1.1/'
    rdf_namespace = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
    authors: list[str] = []

    for creator in root.findall(f'.//{{{dc_namespace}}}creator'):
        list_items = creator.findall(f'.//{{{rdf_namespace}}}li')

        if list_items:
            candidates = (''.join(item.itertext()) for item in list_items)
        else:
            candidates = (''.join(creator.itertext()),)

        authors.extend(candidates)

    return _normalise_authors(authors)


def _normalise_authors(value: object) -> list[str]:
    """Return de-duplicated author names without guessing separators."""
    if value is None:
        return []

    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, Sequence):
        candidates = [str(item) for item in value if item is not None]
    else:
        candidates = [str(value)]

    authors: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        author = candidate.strip()
        normalized = author.casefold()

        if not author or normalized in seen:
            continue

        seen.add(normalized)
        authors.append(author)

    return authors


def _parse_legacy_authors(value: str | None) -> list[str]:
    """Parse multiple authors from the legacy single-string field.

    Only semicolons and line breaks are treated as separators. Commas are
    preserved because they commonly occur inside names such as
    ``"Lhomond, Alexandra"``.
    """
    if value is None:
        return []

    return _normalise_authors(re.split(r'[;\n]+', value))

def _normalise_keywords(value: object) -> list[str]:
    """Return normalized, de-duplicated keyword strings."""
    if value is None:
        return []

    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, Sequence):
        candidates = [str(item) for item in value if item is not None]
    else:
        candidates = [str(value)]

    keywords: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        for part in re.split(r'[,;\n]+', candidate):
            keyword = part.strip()
            normalized = keyword.casefold()

            if not keyword or normalized in seen:
                continue

            seen.add(normalized)
            keywords.append(keyword)

    return keywords


def _clean_optional_text(value: str | None) -> str | None:
    """Return stripped non-empty text, otherwise ``None``."""
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None


def _metadata_value(
    metadata: dict[str, str],
    key: str,
) -> str | None:
    """Read a metadata value while ignoring key spelling and punctuation."""
    expected_key = re.sub(r'[^a-z0-9]', '', key.casefold())

    for candidate_key, candidate_value in metadata.items():
        normalized_key = re.sub(
            r'[^a-z0-9]',
            '',
            candidate_key.casefold(),
        )
        if normalized_key == expected_key:
            return _clean_optional_text(candidate_value)

    return None


def _parse_pdf_metadata_date(value: str | None) -> date | None:
    """Parse the calendar date portion of a standard PDF date string."""
    if value is None:
        return None

    match = re.search(r'(?:D:)?(\d{4})(\d{2})?(\d{2})?', value)
    if match is None:
        return None

    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)

    try:
        return date(year, month, day)
    except ValueError:
        return None


def _normalise_metadata(
    metadata: dict[str, str] | None,
) -> dict[str, str]:
    """Return non-empty PDF metadata with stable title-cased keys."""
    if not metadata:
        return {}

    return {
        key.replace('_', ' ').title().replace(' ', ''): str(value)
        for key, value in metadata.items()
        if value not in (None, '')
    }


@dataclass(slots=True)
class _SectionBuilder:
    title: str | None
    level: int | None
    page_start: int
    own_page_end: int
    paragraphs: tuple[ParsedParagraph, ...]
    children: list[_SectionBuilder] = field(default_factory=list)


def _nest_sections(
    flat_sections: tuple[ParsedSection, ...],
) -> tuple[ParsedSection, ...]:
    """Nest flat sections according to their inferred heading levels."""
    roots: list[_SectionBuilder] = []
    stack: list[_SectionBuilder] = []

    for section in flat_sections:
        builder = _SectionBuilder(
            title=section.title,
            level=section.level,
            page_start=section.page_start,
            own_page_end=section.page_end,
            paragraphs=section.paragraphs,
        )

        if section.level is None:
            roots.append(builder)
            stack.clear()
            continue

        while (
            stack and stack[-1].level is not None and stack[-1].level >= section.level
        ):
            stack.pop()

        if stack:
            stack[-1].children.append(builder)
        else:
            roots.append(builder)

        stack.append(builder)

    return tuple(_freeze_section(root) for root in roots)


def _freeze_section(builder: _SectionBuilder) -> ParsedSection:
    """Convert a mutable section builder into an immutable parsed section."""
    subsections = tuple(_freeze_section(child) for child in builder.children)

    page_end = max(
        (
            builder.own_page_end,
            *(child.page_end for child in subsections),
        )
    )

    return ParsedSection(
        title=builder.title,
        level=builder.level,
        page_start=builder.page_start,
        page_end=page_end,
        paragraphs=builder.paragraphs,
        subsections=subsections,
    )
