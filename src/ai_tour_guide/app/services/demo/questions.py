"""Question data used by the built-in demo experience."""

import json
import random
from dataclasses import dataclass
from pathlib import Path

from ai_tour_guide.app.agent.identity import WELCOME_MESSAGE

DEFAULT_DEMO_DATASET_PATH = Path(__file__).parent / 'data' / 'demo_dataset.jsonl'
DEFAULT_CLOSE_QUESTION_DISTANCE = 0.25
DEFAULT_SIMILAR_QUESTION_DISTANCE = 0.50
DEMO_LIMITATION_MESSAGE = (
    'This is a limited experience with prepared Brittany questions. '
    'It accepts modest spelling and punctuation variations.'
)
DEMO_WELCOME_MESSAGE = WELCOME_MESSAGE


@dataclass(frozen=True, slots=True)
class DemoResponse:
    """A response selected from the deterministic demo dataset."""

    text: str


class DeterministicQuestionsService:
    """Resolve demo questions directly from the bundled JSONL dataset."""

    def __init__(
        self,
        dataset_path: Path = DEFAULT_DEMO_DATASET_PATH,
        *,
        close_question_distance: float = DEFAULT_CLOSE_QUESTION_DISTANCE,
        similar_question_distance: float = DEFAULT_SIMILAR_QUESTION_DISTANCE,
    ) -> None:
        self.dataset_path = dataset_path
        self.close_question_distance = close_question_distance
        self.similar_question_distance = similar_question_distance
        self._answers = _load_answers(dataset_path)

    def answer(self, question: str) -> DemoResponse:
        """Return a prepared answer, suggestion, or general fallback."""
        answer = self._answers.get(question)
        if answer is None:
            matched_question = _closest_question(
                question,
                self._answerable_questions,
                max_distance=self.close_question_distance,
            )
            answer = self._answers[matched_question] if matched_question else None
        if answer is not None:
            return DemoResponse(answer)
        if question in self._answers:
            return self._fallback_response()
        similar_question = _closest_question(
            question,
            self._answerable_questions,
            max_distance=self.similar_question_distance,
        )
        if similar_question is not None:
            return DemoResponse(
                f'{DEMO_LIMITATION_MESSAGE}\n\nDid you mean: “{similar_question}”?'
            )
        return self._fallback_response()

    @property
    def _answerable_questions(self) -> tuple[str, ...]:
        return tuple(
            question for question, answer in self._answers.items() if answer is not None
        )

    def _fallback_response(self) -> DemoResponse:
        if not self._answerable_questions:
            raise ValueError('The demo dataset does not contain prepared questions.')
        suggestion = random.choice(self._answerable_questions)
        return DemoResponse(f'{DEMO_LIMITATION_MESSAGE}\n\nTry asking: “{suggestion}”')


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


def _load_answers(dataset_path: Path) -> dict[str, str | None]:
    """Load the question-to-answer portion of the demo dataset."""
    try:
        lines = dataset_path.read_text(encoding='utf-8').splitlines()
    except OSError as exc:
        raise ValueError(f'Unable to read demo dataset {dataset_path}.') from exc

    answers: dict[str, str | None] = {}
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
        if question in answers:
            raise ValueError(
                f'Duplicate demo question at {dataset_path}:{line_number}.'
            )
        answers[question] = answer
    return answers


def _closest_question(
    question: str,
    candidates: tuple[str, ...],
    *,
    max_distance: float,
) -> str | None:
    if not candidates:
        return None
    closest = min(
        candidates,
        key=lambda candidate: _normalized_question_distance(question, candidate),
    )
    if _normalized_question_distance(question, closest) <= max_distance:
        return closest
    return None


def _normalized_question_distance(first: str, second: str) -> float:
    first = ' '.join(first.casefold().split())
    second = ' '.join(second.casefold().split())
    if not first and not second:
        return 0.0
    previous = list(range(len(second) + 1))
    for first_index, first_character in enumerate(first, start=1):
        current = [first_index]
        for second_index, second_character in enumerate(second, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[second_index] + 1,
                    previous[second_index - 1] + (first_character != second_character),
                )
            )
        previous = current
    return previous[-1] / max(len(first), len(second))


__all__ = [
    'DEFAULT_DEMO_DATASET_PATH',
    'DEMO_LIMITATION_MESSAGE',
    'DEMO_WELCOME_MESSAGE',
    'DemoResponse',
    'DeterministicQuestionsService',
    'load_demo_questions',
]
