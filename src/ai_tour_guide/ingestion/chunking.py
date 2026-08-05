from __future__ import annotations

import json

import click
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


_SENTENCE_BOUNDARY_RE = re.compile(r'(?<=[.!?])\s+')
_WHITESPACE_RE = re.compile(r'\s+')


@dataclass(frozen=True, slots=True)
class Paragraph:
    """A normalized paragraph extracted from the parser output."""

    text: str
    page_start: int | None = None
    page_end: int | None = None


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
            )


def _min_page(values: Iterable[int | None]) -> int | None:
    pages = [value for value in values if value is not None]
    return min(pages) if pages else None


def _max_page(values: Iterable[int | None]) -> int | None:
    pages = [value for value in values if value is not None]
    return max(pages) if pages else None


def _pack_section_paragraphs(
    paragraphs: Iterable[dict[str, Any]],
    max_chars: int,
) -> Iterator[tuple[str, int | None, int | None]]:
    """
    Greedily pack consecutive paragraphs from one section.

    Paragraph boundaries are represented by a blank line. No output text exceeds
    max_chars. Content from different sections is never mixed.
    """
    current: list[Paragraph] = []
    current_length = 0
    separator_length = len('\n\n')

    for paragraph in _expanded_paragraphs(paragraphs, max_chars):
        candidate_length = (
            len(paragraph.text)
            if not current
            else current_length + separator_length + len(paragraph.text)
        )

        if current and candidate_length > max_chars:
            yield (
                _join_parts([item.text for item in current]),
                _min_page(item.page_start for item in current),
                _max_page(item.page_end for item in current),
            )
            current = [paragraph]
            current_length = len(paragraph.text)
        else:
            current.append(paragraph)
            current_length = candidate_length

    if current:
        yield (
            _join_parts([item.text for item in current]),
            _min_page(item.page_start for item in current),
            _max_page(item.page_end for item in current),
        )


def _embedding_text(section_path: Sequence[str], text: str) -> str:
    heading_text = '\n'.join(title for title in section_path if title)
    return f'{heading_text}\n\n{text}' if heading_text else text


def chunk_document(document: dict[str, Any], max_chars: int = 1_000) -> list[Chunk]:
    """
    Convert parser JSON into structure-aware chunks.

    Each section's own paragraphs are packed independently. The function then
    recursively processes its subsections, so section boundaries are never
    crossed. The size limit applies to Chunk.text, not embedding_text.
    """
    if max_chars <= 0:
        raise ValueError('max_chars must be greater than zero')

    document_title = _normalize_text(document.get('title')) or 'Untitled document'
    slug = _document_slug(document_title)
    chunks: list[Chunk] = []

    def visit(section: dict[str, Any], parent_path: tuple[str, ...]) -> None:
        title = _normalize_text(section.get('title'))
        section_path = parent_path + ((title,) if title else ())

        raw_paragraphs = section.get('paragraphs') or []
        if not isinstance(raw_paragraphs, list):
            raise TypeError('section.paragraphs must be a list')

        for text, page_start, page_end in _pack_section_paragraphs(
            raw_paragraphs,
            max_chars=max_chars,
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
        visit(section, ())

    return chunks


def load_chunks(path: str | Path, max_chars: int = 1_000) -> list[Chunk]:
    """Load a parser JSON file and return its chunks."""
    input_path = Path(path)
    with input_path.open('r', encoding='utf-8') as file:
        document = json.load(file)

    if not isinstance(document, dict):
        raise TypeError('The JSON root must be an object')

    return chunk_document(document, max_chars=max_chars)


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
    '--max-chars',
    type=click.IntRange(min=1),
    default=1_000,
    show_default=True,
    help='Maximum characters in Chunk.text.',
)
def main(input_path: Path, output_path: Path | None, max_chars: int) -> None:
    """Convert parser JSON into structure-aware retrieval chunks.

    INPUT_PATH is the JSON document generated by the PDF parser.
    """
    try:
        chunks = load_chunks(input_path, max_chars=max_chars)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if output_path is not None:
        try:
            write_chunks(chunks, output_path)
        except OSError as exc:
            raise click.ClickException(str(exc)) from exc

    largest = max((chunk.character_count for chunk in chunks), default=0)
    click.echo(f'Generated {len(chunks)} chunks')
    click.echo(f'Largest chunk: {largest} characters')
    if output_path is not None:
        click.echo(f'Wrote: {output_path}')


if __name__ == '__main__':
    main()
