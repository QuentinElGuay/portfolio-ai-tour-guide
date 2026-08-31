"""Deterministic test-only LLM backed by golden-dataset answers."""

import json
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.llm.clients import GenerationError
from ai_tour_guide.agent.rag.models import GeneratedAnswer, LLMCitation
from ai_tour_guide.agent.responses import INSUFFICIENT_CONTEXT_ANSWER
from ai_tour_guide.domain.sections import slugify_section_path

_QUESTION_MARKER = 'User question:\n'
_CLOSE_QUESTION_DISTANCE = 0.15
_SIMILAR_QUESTION_DISTANCE = 0.40
_CONTEXT_PATTERN = re.compile(
    r'^Source: .*?\n'
    r'URL: (?P<source_url>.+)\n'
    r'Version: (?P<version>.+)\n'
    r'Pages: (?P<pages>.*)\n'
    r'Section: (?P<section>.+)$',
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class FixtureCase:
    """The golden-dataset information needed by the fixture client."""

    answerable: bool
    answer: str | None
    source_url: str | None
    version: str | None
    section_path: tuple[str, ...] | None


class FixtureLLMClient:
    """Return golden answers only when their expected evidence was retrieved."""

    def __init__(self, dataset_path: Path) -> None:
        self.dataset_path = dataset_path
        self._cases = _load_cases(dataset_path)

    async def answer_question(self, messages: Sequence[Message]) -> GeneratedAnswer:
        """Return the golden answer and a page derived from supplied context."""
        question = _question_from_messages(messages)
        case = self._cases.get(question)
        return self._answer_case(messages, question, case)

    def _answer_case(
        self,
        messages: Sequence[Message],
        question: str,
        case: FixtureCase | None,
    ) -> GeneratedAnswer:
        """Return the answer for a known fixture question."""
        if case is None:
            raise GenerationError(f'No fixture answer is configured for {question!r}.')
        if not case.answerable:
            return GeneratedAnswer(
                INSUFFICIENT_CONTEXT_ANSWER,
                llm_metadata={'provider': 'fixture', 'dataset': str(self.dataset_path)},
            )

        context = _matching_context(messages, case)
        if context is None:
            raise GenerationError(
                f'Expected fixture evidence was not retrieved for {question!r}; '
                f'available contexts: {_context_descriptions(messages)!r}.'
            )
        source_url, version, pages = context
        return GeneratedAnswer(
            case.answer or '',
            citations=(LLMCitation(source_url, version, pages[0], pages[0]),),
            llm_metadata={'provider': 'fixture', 'dataset': str(self.dataset_path)},
        )


class BaguetteLLMClient(FixtureLLMClient):
    """A friendly, zero-cost Brittany demo backed by golden-dataset answers."""

    def __init__(self, dataset_path: Path) -> None:
        super().__init__(dataset_path)
        self._answerable_questions = tuple(
            question for question, case in self._cases.items() if case.answerable
        )

    async def answer_question(self, messages: Sequence[Message]) -> GeneratedAnswer:
        """Return a prepared answer or suggest a question the demo can answer."""
        question = _question_from_messages(messages)
        exact_case = self._cases.get(question)
        if exact_case is not None and exact_case.answerable:
            matched_question = question
        else:
            matched_question = _closest_question(
                question,
                self._answerable_questions,
                max_distance=_CLOSE_QUESTION_DISTANCE,
            )
        if matched_question is not None:
            case = self._cases[matched_question]
            if case.answerable and _matching_context(messages, case) is not None:
                generated = self._answer_case(messages, matched_question, case)
                return GeneratedAnswer(
                    generated.answer,
                    citations=generated.citations,
                    emotion=generated.emotion,
                    llm_metadata={
                        'provider': 'baguette-llm',
                        'dataset': str(self.dataset_path),
                    },
                    raw_provider_response=generated.raw_provider_response,
                )
        if exact_case is not None:
            return self._fallback_answer()

        somewhat_similar_question = _closest_question(
            question,
            self._answerable_questions,
            max_distance=_SIMILAR_QUESTION_DISTANCE,
        )
        if somewhat_similar_question is not None:
            return self._did_you_mean_answer(somewhat_similar_question)
        return self._fallback_answer()

    def _did_you_mean_answer(self, suggestion: str) -> GeneratedAnswer:
        return GeneratedAnswer(
            'This is a demo backend with limited knowledge of Brittany, so I do not '
            f'have a prepared answer for that question. Did you mean: “{suggestion}”?',
            llm_metadata={
                'provider': 'baguette-llm',
                'dataset': str(self.dataset_path),
            },
        )

    def _fallback_answer(self) -> GeneratedAnswer:
        if not self._answerable_questions:
            raise GenerationError(
                'The demo fixture does not contain answerable questions.'
            )
        suggestion = random.choice(self._answerable_questions)
        return GeneratedAnswer(
            'This is a demo backend with limited knowledge of Brittany, so I do not '
            f'have a prepared answer for that question. Try asking: “{suggestion}”',
            llm_metadata={
                'provider': 'baguette-llm',
                'dataset': str(self.dataset_path),
            },
        )


def _load_cases(dataset_path: Path) -> dict[str, FixtureCase]:
    """Load the golden dataset without importing evaluation-only code at runtime."""
    try:
        lines = dataset_path.read_text(encoding='utf-8').splitlines()
    except OSError as exc:
        raise ValueError(f'Unable to read fixture dataset {dataset_path}.') from exc

    cases: dict[str, FixtureCase] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            expected = row['expected']
            answerable = expected['answerable']
            source = expected.get('relevant_source')
            question = row['question']
            if not isinstance(question, str) or not isinstance(answerable, bool):
                raise TypeError('question and answerable must be correctly typed')
            case = FixtureCase(
                answerable=answerable,
                answer=expected['reference_answer'],
                source_url=source['source_url'] if source else None,
                version=source['version'] if source else None,
                section_path=(
                    slugify_section_path(source['section_path']) if source else None
                ),
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f'Invalid fixture dataset row at {dataset_path}:{line_number}.'
            ) from exc
        if question in cases:
            raise ValueError(
                f'Duplicate fixture question at {dataset_path}:{line_number}.'
            )
        cases[question] = case
    return cases


def load_answerable_questions(dataset_path: Path) -> tuple[str, ...]:
    """Return the questions with prepared answers in a fixture dataset."""
    return tuple(
        question
        for question, case in _load_cases(dataset_path).items()
        if case.answerable
    )


def _question_from_messages(messages: Sequence[Message]) -> str:
    for message in reversed(messages):
        content = message['content']
        if _QUESTION_MARKER in content:
            return content.rsplit(_QUESTION_MARKER, maxsplit=1)[1].strip()
    raise GenerationError('Fixture prompt does not contain a user question.')


def _closest_question(
    question: str,
    candidates: Sequence[str],
    *,
    max_distance: float,
) -> str | None:
    """Return the closest prepared question when it is within the allowed margin."""
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
    """Compute the Levenshtein distance between two questions as a ratio."""
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


def _matching_context(
    messages: Sequence[Message], case: FixtureCase
) -> tuple[str, str | None, tuple[int, ...]] | None:
    if case.source_url is None or case.section_path is None:
        return None
    content = '\n'.join(message['content'] for message in messages)
    for match in _CONTEXT_PATTERN.finditer(content):
        source_url = match['source_url']
        version = None if match['version'] == 'null' else match['version']
        section_path = slugify_section_path(match['section'].split(' > '))
        pages = tuple(int(page) for page in match['pages'].split(', ') if page)
        if (
            source_url == case.source_url
            and version == case.version
            and section_path[:-1] == case.section_path
            and pages
        ):
            return source_url, version, pages
    return None


def _context_descriptions(messages: Sequence[Message]) -> tuple[str, ...]:
    """Return concise prompt provenance to make fixture failures actionable."""
    content = '\n'.join(message['content'] for message in messages)
    return tuple(
        f'{match["source_url"]} | {match["section"]}'
        for match in _CONTEXT_PATTERN.finditer(content)
    )


__all__ = [
    'BaguetteLLMClient',
    'FixtureLLMClient',
    'load_answerable_questions',
]
