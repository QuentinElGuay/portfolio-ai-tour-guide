"""Deterministic client for the bundled application demo."""

import json
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ai_tour_guide.app.agent.demo_questions import DEFAULT_DEMO_DATASET_PATH
from ai_tour_guide.app.agent.llm.clients import GenerationError
from ai_tour_guide.app.agent.llm.settings import (
    DEFAULT_CLOSE_QUESTION_DISTANCE,
    DEFAULT_SIMILAR_QUESTION_DISTANCE,
)
from ai_tour_guide.app.agent.rag.models import GeneratedAnswer, LLMCitation
from ai_tour_guide.app.chat.models import Message
from ai_tour_guide.domain.sections import slugify_section_path

_QUESTION_MARKER = 'User question:\n'
_DEMO_LIMITATION_MESSAGE = (
    'This is a demo backend with limited knowledge of Brittany, so I do not have a '
    'prepared answer for that question.'
)
_CONTEXT_PATTERN = re.compile(
    r'^Source: .*?\n'
    r'URL: (?P<source_url>.+)\n'
    r'Version: (?P<version>.+)\n'
    r'Pages: (?P<pages>.*)\n'
    r'Section: (?P<section>.+)$',
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class DemoCase:
    """One prepared answer in the standalone demo dataset."""

    answer: str | None
    source_url: str | None
    version: str | None
    section_path: tuple[str, ...] | None
    pages: tuple[int, ...]


class DemoLLMClient:
    """Return deterministic answers from the bundled demo dataset."""

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
        self._cases = _load_cases(dataset_path)
        self._answerable_questions = tuple(
            question
            for question, case in self._cases.items()
            if case.answer is not None
        )

    async def answer_question(self, messages: Sequence[Message]) -> GeneratedAnswer:
        """Return a prepared demo answer, suggestion, or generic fallback."""
        question = _question_from_messages(messages)
        return self._answer_demo_question(messages, question)

    async def choose_search_query(
        self,
        question: str,
        *,
        previous_queries: Sequence[str],
        has_context: bool,
    ) -> str | None:
        """Use the original question once for deterministic demo retrieval."""
        del has_context
        return None if previous_queries else question

    def _answer_demo_question(
        self, messages: Sequence[Message], question: str
    ) -> GeneratedAnswer:
        """Return a prepared demo answer or a useful question suggestion."""
        exact_case = self._cases.get(question)
        if exact_case is not None and exact_case.answer is not None:
            matched_question = question
        else:
            matched_question = _closest_question(
                question,
                self._answerable_questions,
                max_distance=self.close_question_distance,
            )
        if matched_question is not None:
            case = self._cases[matched_question]
            if (
                case.answer is not None
                and _matching_context(messages, case) is not None
            ):
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
            max_distance=self.similar_question_distance,
        )
        if somewhat_similar_question is not None:
            return self._did_you_mean_answer(somewhat_similar_question)
        return self._fallback_answer()

    def _answer_case(
        self,
        messages: Sequence[Message],
        question: str,
        case: DemoCase | None,
    ) -> GeneratedAnswer:
        """Return the answer for a known demo question."""
        if case is None:
            return self._fallback_answer()

        context = _matching_context(messages, case)
        if context is None:
            raise GenerationError(
                f'Expected demo evidence was not retrieved for {question!r}; '
                f'available contexts: {_context_descriptions(messages)!r}.'
            )
        source_url, version, pages = context
        return GeneratedAnswer(
            case.answer or '',
            citations=(LLMCitation(source_url, version, pages[0], pages[0]),),
            llm_metadata={
                'provider': 'baguette-llm',
                'dataset': str(self.dataset_path),
            },
        )

    def _did_you_mean_answer(self, suggestion: str) -> GeneratedAnswer:
        return GeneratedAnswer(
            f'{_DEMO_LIMITATION_MESSAGE}\n\nDid you mean: “{suggestion}”?',
            llm_metadata={
                'provider': 'baguette-llm',
                'dataset': str(self.dataset_path),
            },
        )

    def _fallback_answer(self) -> GeneratedAnswer:
        if not self._answerable_questions:
            raise GenerationError(
                'The demo dataset does not contain prepared questions.'
            )
        suggestion = random.choice(self._answerable_questions)
        return GeneratedAnswer(
            f'{_DEMO_LIMITATION_MESSAGE}\n\nTry asking: “{suggestion}”',
            llm_metadata={
                'provider': 'baguette-llm',
                'dataset': str(self.dataset_path),
            },
        )


def _load_cases(dataset_path: Path) -> dict[str, DemoCase]:
    """Load and validate the standalone demo JSONL schema."""
    try:
        lines = dataset_path.read_text(encoding='utf-8').splitlines()
    except OSError as exc:
        raise ValueError(f'Unable to read demo dataset {dataset_path}.') from exc

    cases: dict[str, DemoCase] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            question = row['question']
            answer = row['answer']
            source = row.get('source')
            if not isinstance(question, str) or (
                answer is not None and not isinstance(answer, str)
            ):
                raise TypeError('question and answer must be correctly typed')
            if source is not None and not isinstance(source, dict):
                raise TypeError('source must be an object or null')
            case = DemoCase(
                answer=answer,
                source_url=source['source_url'] if source else None,
                version=source.get('version') if source else None,
                section_path=(
                    slugify_section_path(source['section_path']) if source else None
                ),
                pages=tuple(source.get('pages', ())) if source else (),
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f'Invalid demo dataset row at {dataset_path}:{line_number}.'
            ) from exc
        if question in cases:
            raise ValueError(
                f'Duplicate demo question at {dataset_path}:{line_number}.'
            )
        cases[question] = case
    return cases


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
    messages: Sequence[Message], case: DemoCase
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
    """Return concise prompt provenance to make demo failures actionable."""
    content = '\n'.join(message['content'] for message in messages)
    return tuple(
        f'{match["source_url"]} | {match["section"]}'
        for match in _CONTEXT_PATTERN.finditer(content)
    )


__all__ = [
    'DemoCase',
    'DemoLLMClient',
]
