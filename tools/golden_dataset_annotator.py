"""Interactively annotate reference answers and source pages in a golden dataset."""

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import questionary

DEFAULT_INPUT = Path('evaluation/datasets/golden_dataset.jsonl')


def parse_pages(value: str) -> list[int]:
    """Parse a comma-separated list of one-indexed source pages."""
    try:
        pages = sorted({int(page.strip()) for page in value.split(',') if page.strip()})
    except ValueError as exc:
        raise ValueError('Pages must be comma-separated positive integers.') from exc
    if not pages or any(page <= 0 for page in pages):
        raise ValueError('Enter at least one positive page number.')
    return pages


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
    """Return the next row marked as requiring annotation, if any."""
    for index in range(start_index, len(rows)):
        if rows[index].get('_todo') is True:
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


def update_row(row: dict[str, Any], *, answer: str, pages: list[int]) -> None:
    """Update a row's reference answer and pages for its first source."""
    expected = row['expected']
    sources = expected['relevant_sources']
    if not sources:
        raise ValueError('The question has no relevant source to annotate.')
    expected['reference_answer'] = answer
    sources[0]['pages'] = pages
    row.pop('_todo', None)


def _pages_text(row: dict[str, Any]) -> str:
    sources = row['expected']['relevant_sources']
    if not sources:
        return ''
    return ', '.join(str(page) for page in sources[0]['pages'])


def _show_question(row: dict[str, Any], *, position: int, total: int) -> None:
    print(f'\nQuestion {row["id"]} ({position}/{total})')
    print(f'Category: {row["category"]}')
    print(row['question'])
    print(f'Current answer: {row["expected"]["reference_answer"] or "(missing)"}')
    print(f'Current pages: {_pages_text(row) or "(missing)"}')


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
                'Edit answer and pages',
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
        pages_text = questionary.text('Source page(s):', default=_pages_text(row)).ask()
        if answer is None or pages_text is None:
            continue
        if not answer.strip():
            print('Reference answer cannot be empty.')
            continue
        try:
            update_row(row, answer=answer.strip(), pages=parse_pages(pages_text))
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
        description='Fill in reference answers and source pages in a golden dataset.'
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
