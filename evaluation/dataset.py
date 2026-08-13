"""Golden-dataset loading utilities."""

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATASET_ROOT = Path('evaluation/datasets')
GOLDEN_DATASET_FILENAME = 'golden_dataset.jsonl'


@dataclass(frozen=True, slots=True)
class SourceExpectation:
    source_url: str
    version: str | None
    pages: tuple[int, ...]
    section_paths: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class ExpectedOutcome:
    answerable: bool
    reference_answer: str | None
    relevant_sources: tuple[SourceExpectation, ...]


@dataclass(frozen=True, slots=True)
class GoldenCase:
    case_id: int
    question: str
    category: str
    expected: ExpectedOutcome


def golden_dataset_path(*, root: Path = DEFAULT_DATASET_ROOT) -> Path:
    """Return the path to the unversioned golden dataset."""
    return root / GOLDEN_DATASET_FILENAME


def load_golden_dataset(
    *,
    root: Path = DEFAULT_DATASET_ROOT,
) -> list[GoldenCase]:
    """Load document/page and answer expectations from a JSONL dataset."""
    path = golden_dataset_path(root=root)
    cases: list[GoldenCase] = []

    with path.open(encoding='utf-8') as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            raw = json.loads(line)
            try:
                case_id = raw['id']
                if not isinstance(case_id, int) or isinstance(case_id, bool):
                    raise TypeError('id must be an integer')
                expected = raw['expected']
                relevant_sources = tuple(
                    SourceExpectation(
                        source_url=source['source_url'],
                        version=source['version'],
                        pages=tuple(source['pages']),
                        section_paths=tuple(
                            tuple(section_path)
                            for section_path in source.get('section_paths', [])
                        ),
                    )
                    for source in expected['relevant_sources']
                )
                case = GoldenCase(
                    case_id=case_id,
                    question=raw['question'],
                    category=raw['category'],
                    expected=ExpectedOutcome(
                        answerable=expected['answerable'],
                        reference_answer=expected['reference_answer'],
                        relevant_sources=relevant_sources,
                    ),
                )
            except (KeyError, TypeError) as exc:
                raise ValueError(
                    f'Invalid golden dataset row at {path}:{line_number}'
                ) from exc

            cases.append(case)

    return cases
