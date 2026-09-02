"""Interactively annotate reference answers and source sections in a golden dataset."""

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import questionary

from ai_tour_guide.knowledge_base import slugify_section_path

DEFAULT_INPUT = Path('evaluation/datasets/golden_dataset.jsonl')


def parse_section_path(value: str) -> list[str]:
    """Parse a ``>``-separated source section path into stable slugs."""
    parts = [part.strip() for part in value.split('>')]
    if not parts or any(not part for part in parts):
        raise ValueError('Section path must contain non-empty headings separated by >.')
    section_path = list(slugify_section_path(parts))
    if not all(section_path):
        raise ValueError('Section path must contain at least one letter or number.')
    return section_path


def load_rows(path: Path) -> list[dict[str, Any]]:
    """Load JSONL rows while retaining fields not used by this tool."""
    with path.open(encoding='utf-8') as dataset:
        rows = [json.loads(line) for line in dataset if line.strip()]
    for row in rows:
        missing = {'id', 'category', 'question', 'expected'} - row.keys()
        if missing:
            raise ValueError(
                f'Invalid dataset row {row.get("id", "?")}: missing '
                f'{", ".join(sorted(missing))}'
            )
    return rows


def write_rows(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """Write the working dataset atomically in JSONL format."""
    temporary_path = path.with_suffix(f'{path.suffix}.tmp')
    with temporary_path.open('w', encoding='utf-8') as dataset:
        for row in rows:
            dataset.write(json.dumps(row, ensure_ascii=False))
            dataset.write('\n')
    temporary_path.replace(path)


def find_row(rows: list[dict[str, Any]], case_id: int) -> int:
    """Return the index of the row with ``case_id``."""
    for index, row in enumerate(rows):
        if row.get('id') == case_id:
            return index
    raise ValueError(f'Question ID {case_id} was not found.')


def find_next_unanswered(
    rows: list[dict[str, Any]], *, start_index: int = 0
) -> int | None:
    """Return the next answerable row missing an answer or source section."""
    for index in range(start_index, len(rows)):
        expected = rows[index]['expected']
        source = expected.get('relevant_source')
        if rows[index].get('_todo') is True or (
            expected.get('answerable') is True
            and (
                not expected.get('reference_answer')
                or not isinstance(source, dict)
                or not source.get('section_path')
            )
        ):
            return index
    return None


def initial_index(
    rows: list[dict[str, Any]], *, start_id: int | None, resume: bool
) -> int | None:
    """Choose the initial row for a new sequential run or a resumed run."""
    if start_id is not None:
        return find_row(rows, start_id)
    if resume:
        return find_next_unanswered(rows)
    return 0 if rows else None


def next_index(rows: list[dict[str, Any]], *, index: int, resume: bool) -> int | None:
    """Advance sequentially, or only across unanswered rows when resuming."""
    if resume:
        return find_next_unanswered(rows, start_index=index + 1)
    return index + 1 if index + 1 < len(rows) else None


def update_row(row: dict[str, Any], *, answer: str, section_path: list[str]) -> None:
    """Update a row's reference answer and stable source section path."""
    expected = row['expected']
    source = expected.get('relevant_source')
    if expected.get('answerable') is not True or not isinstance(source, dict):
        raise ValueError('The question has no relevant source to annotate.')
    expected['reference_answer'] = answer
    source['section_path'] = section_path
    row.pop('_todo', None)


def create_row(
    rows: Iterable[dict[str, Any]],
    *,
    category: str,
    question: str,
    answerable: bool,
    reference_answer: str | None = None,
    source_url: str | None = None,
    version: str | None = None,
    section_path: list[str] | None = None,
) -> dict[str, Any]:
    """Create one schema-valid golden-dataset row with the next available ID."""
    normalized_category = category.strip()
    normalized_question = question.strip()
    if not normalized_category or not normalized_question:
        raise ValueError('Category and question cannot be empty.')

    existing_ids: list[int] = []
    for row in rows:
        case_id = row.get('id')
        if not isinstance(case_id, int) or isinstance(case_id, bool):
            raise TypeError('Existing dataset rows must have integer IDs.')
        existing_ids.append(case_id)
    row: dict[str, Any] = {
        'id': max(existing_ids, default=0) + 1,
        'category': normalized_category,
        'question': normalized_question,
        'expected': {
            'answerable': answerable,
            'reference_answer': None,
        },
    }
    if not answerable:
        return row

    if not reference_answer or not reference_answer.strip():
        raise ValueError('Answerable questions require a reference answer.')
    if not source_url or not source_url.strip():
        raise ValueError('Answerable questions require a source URL.')
    if not section_path:
        raise ValueError('Answerable questions require a source section path.')
    row['expected'] = {
        'answerable': True,
        'reference_answer': reference_answer.strip(),
        'relevant_source': {
            'source_url': source_url.strip(),
            'version': version.strip() if version and version.strip() else None,
            'section_path': section_path,
        },
    }
    return row


def _section_path_text(row: dict[str, Any]) -> str:
    source = row['expected'].get('relevant_source')
    if not isinstance(source, dict):
        return ''
    return ' > '.join(source.get('section_path', []))


def _show_question(row: dict[str, Any], *, position: int, total: int) -> None:
    print(f'\nQuestion {row["id"]} ({position}/{total})')
    print(f'Category: {row["category"]}')
    print(row['question'])
    print(f'Current answer: {row["expected"]["reference_answer"] or "(missing)"}')
    print(f'Current source section: {_section_path_text(row) or "(missing)"}')


def _new_question(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prompt for a complete new golden case, returning ``None`` when cancelled."""
    category = questionary.text('Category:').ask()
    question = questionary.text('Question:').ask()
    answerable = questionary.confirm(
        'Is this question answerable from the corpus?'
    ).ask()
    if category is None or question is None or answerable is None:
        return None
    if not answerable:
        return create_row(rows, category=category, question=question, answerable=False)

    answer = questionary.text('Reference answer:').ask()
    source_url = questionary.text('Source URL:').ask()
    version = questionary.text('Source version (optional):').ask()
    section_path = questionary.text(
        'Source section path (use > between headings):'
    ).ask()
    if None in (answer, source_url, version, section_path):
        return None
    return create_row(
        rows,
        category=category,
        question=question,
        answerable=True,
        reference_answer=answer,
        source_url=source_url,
        version=version,
        section_path=parse_section_path(section_path),
    )


def annotate(
    rows: list[dict[str, Any]],
    dataset_path: Path,
    *,
    start_id: int | None,
    resume: bool,
) -> None:
    """Prompt for annotations until the user saves and quits."""
    index = initial_index(rows, start_id=start_id, resume=resume)
    if index is None:
        print('All questions are already answered.')
        return

    while index < len(rows):
        row = rows[index]
        _show_question(row, position=index + 1, total=len(rows))
        action = questionary.select(
            'Choose an action:',
            choices=[
                'Edit answer and source section',
                'Create new question',
                'Next question',
                'Next unanswered question',
                'Jump to question ID',
                'Save and quit',
            ],
        ).ask()

        if action is None or action == 'Save and quit':
            write_rows(dataset_path, rows)
            print(f'Saved dataset to {dataset_path}.')
            return
        if action == 'Create new question':
            try:
                row = _new_question(rows)
            except ValueError as exc:
                print(exc)
                continue
            if row is None:
                continue
            rows.append(row)
            index = len(rows) - 1
            write_rows(dataset_path, rows)
            print(f'Created question {row["id"]} in {dataset_path}.')
            continue
        if action == 'Next question':
            next_question = next_index(rows, index=index, resume=False)
            if next_question is None:
                print('No later questions remain.')
                continue
            index = next_question
            continue
        if action == 'Next unanswered question':
            unanswered_index = find_next_unanswered(rows, start_index=index + 1)
            if unanswered_index is None:
                print('No later unanswered questions remain.')
                continue
            index = unanswered_index
            continue
        if action == 'Jump to question ID':
            target = questionary.text('Question ID:').ask()
            try:
                index = find_row(rows, int(target or ''))
            except ValueError as exc:
                print(exc)
            continue

        answer = questionary.text(
            'Reference answer:', default=row['expected']['reference_answer'] or ''
        ).ask()
        section_path_text = questionary.text(
            'Source section path (use > between headings):',
            default=_section_path_text(row),
        ).ask()
        if answer is None or section_path_text is None:
            continue
        if not answer.strip():
            print('Reference answer cannot be empty.')
            continue
        try:
            update_row(
                row,
                answer=answer.strip(),
                section_path=parse_section_path(section_path_text),
            )
        except ValueError as exc:
            print(exc)
            continue
        write_rows(dataset_path, rows)
        print(f'Saved question {row["id"]} to {dataset_path}.')
        next_question = next_index(rows, index=index, resume=resume)
        if next_question is None:
            break
        index = next_question

    write_rows(dataset_path, rows)
    print(f'All questions are answered. Saved dataset to {dataset_path}.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Fill in reference answers and source sections in a golden dataset.'
    )
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--start-id', type=int, help='Start at this question ID.')
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Start at the first unanswered question and skip answered questions.',
    )
    args = parser.parse_args()

    input_path = args.input.resolve()
    if not input_path.is_file():
        parser.error(f'Input dataset does not exist: {input_path}')

    annotate(
        load_rows(input_path), input_path, start_id=args.start_id, resume=args.resume
    )


if __name__ == '__main__':
    main()
