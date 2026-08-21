"""Deterministic test-only LLM backed by golden-dataset answers."""

import json
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


def _question_from_messages(messages: Sequence[Message]) -> str:
    for message in reversed(messages):
        content = message['content']
        if _QUESTION_MARKER in content:
            return content.rsplit(_QUESTION_MARKER, maxsplit=1)[1].strip()
    raise GenerationError('Fixture prompt does not contain a user question.')


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


__all__ = ['FixtureLLMClient']
