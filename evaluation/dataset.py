"""Versioned golden-dataset loading utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATASET_ROOT = Path("evaluation/datasets")
GOLDEN_DATASET_FILENAME = "golden_dataset.jsonl"


@dataclass(frozen=True, slots=True)
class RetrievalExpectation:
    relevant_chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GoldenCase:
    case_id: str
    question: str
    retrieval: RetrievalExpectation
    # TODO: Add generation expectations when the RAG evaluation schema is
    # finalized (for example required facts, a reference answer, or judge rules).


def golden_dataset_directory(
    version: int,
    *,
    root: Path = DEFAULT_DATASET_ROOT,
) -> Path:
    """Return the directory containing one golden-dataset version."""
    if version <= 0:
        raise ValueError("version must be a positive integer")
    return root / f"v{version}"


def golden_dataset_path(
    version: int,
    *,
    root: Path = DEFAULT_DATASET_ROOT,
) -> Path:
    """Return the expected JSONL path for one golden-dataset version."""
    return golden_dataset_directory(version, root=root) / GOLDEN_DATASET_FILENAME


def load_golden_dataset(
    version: int,
    *,
    root: Path = DEFAULT_DATASET_ROOT,
) -> list[GoldenCase]:
    """Load retrieval expectations from ``root/v{version}/golden_dataset.jsonl``."""
    path = golden_dataset_path(version, root=root)
    cases: list[GoldenCase] = []

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            raw = json.loads(line)
            try:
                relevant_chunk_ids = tuple(raw["retrieval"]["relevant_chunk_ids"])
                case = GoldenCase(
                    case_id=raw["id"],
                    question=raw["question"],
                    retrieval=RetrievalExpectation(relevant_chunk_ids=relevant_chunk_ids),
                )
            except (KeyError, TypeError) as exc:
                raise ValueError(
                    f"Invalid golden dataset row at {path}:{line_number}"
                ) from exc

            cases.append(case)

    return cases
