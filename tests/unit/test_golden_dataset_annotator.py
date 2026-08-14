import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[2] / 'tools' / 'golden_dataset_annotator.py'
SPEC = importlib.util.spec_from_file_location('golden_dataset_annotator', MODULE_PATH)
assert SPEC and SPEC.loader
annotator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(annotator)
find_row = annotator.find_row
find_next_unanswered = annotator.find_next_unanswered
initial_index = annotator.initial_index
next_index = annotator.next_index
parse_pages = annotator.parse_pages
update_row = annotator.update_row


def test_parse_pages_normalizes_duplicates_and_order() -> None:
    assert parse_pages('6, 4, 6') == [4, 6]


@pytest.mark.parametrize('value', ['', '0', 'one'])
def test_parse_pages_rejects_invalid_input(value: str) -> None:
    with pytest.raises(ValueError):
        parse_pages(value)


def test_update_row_replaces_answer_and_pages() -> None:
    row = {
        'id': 1,
        'expected': {
            'reference_answer': None,
            'relevant_sources': [{'pages': [], 'source_url': 'https://example.com'}],
        },
        '_todo': True,
    }

    update_row(row, answer='An answer.', pages=[6])

    assert row['expected']['reference_answer'] == 'An answer.'
    assert row['expected']['relevant_sources'][0]['pages'] == [6]
    assert '_todo' not in row
    assert find_row([row], 1) == 0


def test_find_next_unanswered_uses_boolean_todo_marker() -> None:
    rows = [{'_todo': False}, {'_todo': 'true'}, {'_todo': True}]

    assert find_next_unanswered(rows) == 2
    assert find_next_unanswered(rows, start_index=3) is None


def test_initial_and_next_index_respect_resume_mode() -> None:
    rows = [
        {'id': 1, '_todo': False},
        {'id': 2, '_todo': True},
        {'id': 3, '_todo': True},
    ]

    assert initial_index(rows, start_id=None, resume=False) == 0
    assert initial_index(rows, start_id=None, resume=True) == 1
    assert initial_index(rows, start_id=3, resume=True) == 2
    assert next_index(rows, index=0, resume=False) == 1
    assert next_index(rows, index=1, resume=True) == 2
