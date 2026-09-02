"""Question data used by the built-in demo experience."""

import json
from pathlib import Path

DEFAULT_DEMO_DATASET_PATH = Path(__file__).parent / 'data' / 'demo_dataset.jsonl'


def load_demo_questions(dataset_path: Path) -> tuple[str, ...]:
    """Return questions with prepared answers from a demo dataset."""
    questions: list[str] = []
    try:
        lines = dataset_path.read_text(encoding='utf-8').splitlines()
    except OSError as exc:
        raise ValueError(f'Unable to read demo dataset {dataset_path}.') from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            question = row['question']
            answer = row['answer']
            if not isinstance(question, str) or (
                answer is not None and not isinstance(answer, str)
            ):
                raise TypeError('question and answer must be correctly typed')
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f'Invalid demo dataset row at {dataset_path}:{line_number}.'
            ) from exc
        if answer is not None:
            questions.append(question)
    return tuple(questions)


__all__ = [
    'DEFAULT_DEMO_DATASET_PATH',
    'load_demo_questions',
]
