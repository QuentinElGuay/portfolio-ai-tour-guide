from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import click


_SENTENCE_BOUNDARY_RE = re.compile(r'(?<=[.!?])\s+')
_WHITESPACE_RE = re.compile(r'\s+')
_LABELED_ENTRY_RE = re.compile(r'^[^:\n]{1,80}:\s+\S')


@dataclass(frozen=True, slots=True)
class Paragraph:
    """A normalized paragraph extracted from the parser output."""

    text: str
    page_start: int | None = None
    page_end: int | None = None
    is_labeled_entry: bool = False


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrieval chunk generated from one section of a document."""

    chunk_id: str
    document_title: str
    section_path: tuple[str, ...]
    text: str
    embedding_text: str
    page_start: int | None
    page_end: int | None
    chunk_index: int
    character_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data['section_path'] = list(self.section_path)
        return data


def _normalize_text(value: Any) -> str:
    """Collapse repeated whitespace and return clean text."""
    if value is None:
        return ''
    return _WHITESPACE_RE.sub(' ', str(value)).strip()


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _document_slug(title: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return slug or 'document'


def _document_title(document: dict[str, Any]) -> str:
    """Read the title from parser metadata, with root-level fallback."""
    metadata = document.get('metadata')
    if isinstance(metadata, dict):
        title = _normalize_text(metadata.get('title'))
        if title:
            return title

    return _normalize_text(document.get('title')) or 'Untitled document'


def _is_labeled_entry(text: str) -> bool:
    """Return whether text starts with a short ``Label: value`` pattern."""
    return bool(_LABELED_ENTRY_RE.match(text))


def _join_parts(parts: Sequence[str]) -> str:
    return '\n\n'.join(part for part in parts if part)


def _split_long_word(text: str, max_chars: int) -> list[str]:
    """Last-resort split for text containing a token longer than max_chars."""
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def _split_by_words(text: str, max_chars: int) -> list[str]:
    """Split text on whitespace without producing pieces above max_chars."""
    words = text.split()
    if not words:
        return []

    pieces: list[str] = []
    current: list[str] = []
    current_length = 0

    for word in words:
        if len(word) > max_chars:
            if current:
                pieces.append(' '.join(current))
                current = []
                current_length = 0
            pieces.extend(_split_long_word(word, max_chars))
            continue

        candidate_length = len(word) if not current else current_length + 1 + len(word)
        if current and candidate_length > max_chars:
            pieces.append(' '.join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length = candidate_length

    if current:
        pieces.append(' '.join(current))

    return pieces


def split_oversized_paragraph(text: str, max_chars: int) -> list[str]:
    """
    Split one oversized paragraph, preferring sentence boundaries and then words.

    Every returned piece is non-empty and no longer than max_chars.
    """
    text = _normalize_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = [
        part.strip() for part in _SENTENCE_BOUNDARY_RE.split(text) if part.strip()
    ]
    if len(sentences) == 1:
        return _split_by_words(text, max_chars)

    pieces: list[str] = []
    current: list[str] = []
    current_length = 0

    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                pieces.append(' '.join(current))
                current = []
                current_length = 0
            pieces.extend(_split_by_words(sentence, max_chars))
            continue

        candidate_length = (
            len(sentence) if not current else current_length + 1 + len(sentence)
        )
        if current and candidate_length > max_chars:
            pieces.append(' '.join(current))
            current = [sentence]
            current_length = len(sentence)
        else:
            current.append(sentence)
            current_length = candidate_length

    if current:
        pieces.append(' '.join(current))

    return pieces


def _paragraph_from_dict(data: dict[str, Any]) -> Paragraph | None:
    text = _normalize_text(data.get('text'))
    if not text:
        return None

    return Paragraph(
        text=text,
        page_start=_safe_int(data.get('page_start')),
        page_end=_safe_int(data.get('page_end')),
        is_labeled_entry=_is_labeled_entry(text),
    )


def _expanded_paragraphs(
    paragraphs: Iterable[dict[str, Any]],
    max_chars: int,
) -> Iterator[Paragraph]:
    """Yield normalized paragraphs, splitting any paragraph above max_chars."""
    for raw_paragraph in paragraphs:
        paragraph = _paragraph_from_dict(raw_paragraph)
        if paragraph is None:
            continue

        for piece in split_oversized_paragraph(paragraph.text, max_chars):
            yield Paragraph(
                text=piece,
                page_start=paragraph.page_start,
                page_end=paragraph.page_end,
                is_labeled_entry=paragraph.is_labeled_entry,
            )


def _min_page(values: Iterable[int | None]) -> int | None:
    pages = [value for value in values if value is not None]
    return min(pages) if pages else None


def _max_page(values: Iterable[int | None]) -> int | None:
    pages = [value for value in values if value is not None]
    return max(pages) if pages else None


def _packed_chunk(
    paragraphs: Sequence[Paragraph],
) -> tuple[str, int | None, int | None]:
    return (
        _join_parts([paragraph.text for paragraph in paragraphs]),
        _min_page(paragraph.page_start for paragraph in paragraphs),
        _max_page(paragraph.page_end for paragraph in paragraphs),
    )


def _pack_section_paragraphs(
    paragraphs: Iterable[dict[str, Any]],
    target_chars: int,
    max_chars: int,
) -> Iterator[tuple[str, int | None, int | None]]:
    """
    Pack adjacent unlabeled paragraphs from one section up to a soft target.

    Paragraphs starting with a short ``Label: value`` pattern remain isolated.
    Oversized paragraphs are split before packing. Section boundaries are never
    crossed, and no output text exceeds max_chars.
    """
    current: list[Paragraph] = []
    current_length = 0
    separator_length = len('\n\n')

    for paragraph in _expanded_paragraphs(paragraphs, max_chars):
        if paragraph.is_labeled_entry:
            if current:
                yield _packed_chunk(current)
                current = []
                current_length = 0

            yield _packed_chunk([paragraph])
            continue

        candidate_length = (
            len(paragraph.text)
            if not current
            else current_length + separator_length + len(paragraph.text)
        )

        if current and candidate_length > target_chars:
            yield _packed_chunk(current)
            current = [paragraph]
            current_length = len(paragraph.text)
        else:
            current.append(paragraph)
            current_length = candidate_length

    if current:
        yield _packed_chunk(current)


def _embedding_text(section_path: Sequence[str], text: str) -> str:
    heading_text = '\n'.join(title for title in section_path if title)
    return f'{heading_text}\n\n{text}' if heading_text else text


def _text_limits(
    section_path: Sequence[str],
    target_chars: int,
    max_chars: int,
) -> tuple[int, int]:
    """Reserve space for the breadcrumb included in embedding_text."""
    heading_text = '\n'.join(title for title in section_path if title)
    prefix_length = len(f'{heading_text}\n\n') if heading_text else 0
    text_max_chars = max_chars - prefix_length

    if text_max_chars <= 0:
        raise ValueError(
            'max_chars is too small for the document title and section path'
        )

    text_target_chars = min(max(1, target_chars - prefix_length), text_max_chars)
    return text_target_chars, text_max_chars


def chunk_document(
    document: dict[str, Any],
    target_chars: int = 750,
    max_chars: int = 1_000,
) -> list[Chunk]:
    """
    Convert parser JSON into structure-aware chunks.

    Adjacent unlabeled paragraphs from the same section are joined up to a soft
    target. Labeled entries such as ``Finistère: ...`` remain separate. Long
    paragraphs are split at sentence or word boundaries. The hard limit applies
    to embedding_text, including the document title and section breadcrumb.
    """
    if target_chars <= 0:
        raise ValueError('target_chars must be greater than zero')
    if max_chars <= 0:
        raise ValueError('max_chars must be greater than zero')
    if target_chars > max_chars:
        raise ValueError('target_chars must be less than or equal to max_chars')

    document_title = _document_title(document)
    slug = _document_slug(document_title)
    chunks: list[Chunk] = []

    def visit(section: dict[str, Any], parent_path: tuple[str, ...]) -> None:
        title = _normalize_text(section.get('title'))
        section_path = parent_path + ((title,) if title else ())
        text_target_chars, text_max_chars = _text_limits(
            section_path,
            target_chars,
            max_chars,
        )

        raw_paragraphs = section.get('paragraphs') or []
        if not isinstance(raw_paragraphs, list):
            raise TypeError('section.paragraphs must be a list')

        for text, page_start, page_end in _pack_section_paragraphs(
            raw_paragraphs,
            target_chars=text_target_chars,
            max_chars=text_max_chars,
        ):
            chunk_index = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=f'{slug}:chunk-{chunk_index:04d}',
                    document_title=document_title,
                    section_path=section_path,
                    text=text,
                    embedding_text=_embedding_text(section_path, text),
                    page_start=page_start,
                    page_end=page_end,
                    chunk_index=chunk_index,
                    character_count=len(text),
                )
            )

        subsections = section.get('subsections') or []
        if not isinstance(subsections, list):
            raise TypeError('section.subsections must be a list')

        for subsection in subsections:
            if not isinstance(subsection, dict):
                raise TypeError('Each subsection must be an object')
            visit(subsection, section_path)

    sections = document.get('sections') or []
    if not isinstance(sections, list):
        raise TypeError('document.sections must be a list')

    for section in sections:
        if not isinstance(section, dict):
            raise TypeError('Each section must be an object')
        visit(section, (document_title,))

    return chunks


def load_chunks(
    path: str | Path,
    target_chars: int = 750,
    max_chars: int = 1_000,
) -> list[Chunk]:
    """Load a parser JSON file and return its chunks."""
    input_path = Path(path)
    with input_path.open('r', encoding='utf-8') as file:
        document = json.load(file)

    if not isinstance(document, dict):
        raise TypeError('The JSON root must be an object')

    return chunk_document(
        document,
        target_chars=target_chars,
        max_chars=max_chars,
    )


def write_chunks(chunks: Sequence[Chunk], path: str | Path) -> None:
    """Write chunks as a JSON array."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as file:
        json.dump(
            [chunk.to_dict() for chunk in chunks],
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write('\n')


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.argument(
    'input_path',
    type=click.Path(
        path_type=Path,
        exists=True,
        dir_okay=False,
        readable=True,
    ),
)
@click.option(
    '--output',
    'output_path',
    type=click.Path(path_type=Path, dir_okay=False, writable=True),
    help='Optional output JSON file. When omitted, only a summary is printed.',
)
@click.option(
    '--target-chars',
    type=click.IntRange(min=1),
    default=750,
    show_default=True,
    help='Preferred maximum size of embedding_text when packing paragraphs.',
)
@click.option(
    '--max-chars',
    type=click.IntRange(min=1),
    default=1_000,
    show_default=True,
    help='Hard maximum size of embedding_text.',
)
def main(
    input_path: Path,
    output_path: Path | None,
    target_chars: int,
    max_chars: int,
) -> None:
    """Convert parser JSON into structure-aware retrieval chunks.

    INPUT_PATH is the JSON document generated by the PDF parser.
    """
    try:
        chunks = load_chunks(
            input_path,
            target_chars=target_chars,
            max_chars=max_chars,
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if output_path is not None:
        try:
            write_chunks(chunks, output_path)
        except OSError as exc:
            raise click.ClickException(str(exc)) from exc

    largest = max((len(chunk.embedding_text) for chunk in chunks), default=0)
    click.echo(f'Generated {len(chunks)} chunks')
    click.echo(f'Largest embedding text: {largest} characters')
    if output_path is not None:
        click.echo(f'Wrote: {output_path}')


if __name__ == '__main__':
    main()
