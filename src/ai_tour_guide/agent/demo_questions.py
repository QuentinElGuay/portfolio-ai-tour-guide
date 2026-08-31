"""Question data used by the built-in demo experience."""

import json
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

DEFAULT_BAGUETTE_LLM_DATASET_PATH = files('ai_tour_guide.agent').joinpath(
    'data/demo_dataset.jsonl'
)


def load_answerable_questions(dataset_path: Path | Traversable) -> tuple[str, ...]:
    """Return the questions with prepared answers in a fixture dataset."""
    questions: list[str] = []
    try:
        lines = dataset_path.read_text(encoding='utf-8').splitlines()
    except OSError as exc:
        raise ValueError(f'Unable to read fixture dataset {dataset_path}.') from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            question = row['question']
            answerable = row['expected']['answerable']
            if not isinstance(question, str) or not isinstance(answerable, bool):
                raise TypeError('question and answerable must be correctly typed')
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f'Invalid fixture dataset row at {dataset_path}:{line_number}.'
            ) from exc
        if answerable:
            questions.append(question)
    return tuple(questions)


__all__ = [
    'DEFAULT_BAGUETTE_LLM_DATASET_PATH',
    'load_answerable_questions',
]
