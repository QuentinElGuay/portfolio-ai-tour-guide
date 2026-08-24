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
load_rows = annotator.load_rows
next_index = annotator.next_index
parse_section_path = annotator.parse_section_path
create_row = annotator.create_row
update_row = annotator.update_row
write_rows = annotator.write_rows


class _Prompt:
    """Minimal questionary prompt double that returns one prepared response."""

    def __init__(self, response: object) -> None:
        self.response = response

    def ask(self) -> object:
        """Return the configured response when the annotator requests it."""
        return self.response


def test_parse_section_path_normalizes_headings_to_stable_slugs() -> None:
    """Verify that section paths use the same stable slug format as evaluation."""
    assert parse_section_path("Guide > Côte d'Armor") == ['guide', 'cote-d-armor']


@pytest.mark.parametrize('value', ['', 'Guide > ', ' > Coast', '---'])
def test_parse_section_path_rejects_invalid_input(value: str) -> None:
    """Verify that malformed source section paths are rejected."""
    with pytest.raises(ValueError):
        parse_section_path(value)


def test_update_row_replaces_answer_and_source_section() -> None:
    """Verify that annotation preserves source identity while updating section evidence."""
    row = {
        'id': 1,
        'expected': {
            'reference_answer': None,
            'answerable': True,
            'relevant_source': {
                'source_url': 'https://example.com',
                'version': None,
                'section_path': [],
            },
        },
        '_todo': True,
    }

    update_row(row, answer='An answer.', section_path=['guide', 'coast'])

    assert row['expected']['reference_answer'] == 'An answer.'
    assert row['expected']['relevant_source']['section_path'] == ['guide', 'coast']
    assert '_todo' not in row
    assert find_row([row], 1) == 0


def test_create_row_adds_an_answerable_case_using_current_source_format() -> None:
    """Verify that a new answerable question contains valid provenance and next ID."""
    row = create_row(
        [{'id': 4}],
        category='Transport',
        question='How do I reach Dinan?',
        answerable=True,
        reference_answer='Take the regional train.',
        source_url='https://example.test/guide.pdf',
        version='2026',
        section_path=['guide', 'transport'],
    )

    assert row == {
        'id': 5,
        'category': 'Transport',
        'question': 'How do I reach Dinan?',
        'expected': {
            'answerable': True,
            'reference_answer': 'Take the regional train.',
            'relevant_source': {
                'source_url': 'https://example.test/guide.pdf',
                'version': '2026',
                'section_path': ['guide', 'transport'],
            },
        },
    }


def test_create_row_adds_an_unsupported_case_without_source_evidence() -> None:
    """Verify that a new unsupported question omits answer and source fields."""
    row = create_row(
        [],
        category='Current information',
        question='What is the weather in Brest today?',
        answerable=False,
    )

    assert row['id'] == 1
    assert row['expected'] == {'answerable': False, 'reference_answer': None}


def test_annotate_creates_and_persists_a_new_answerable_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that the create menu action collects and saves a complete new case."""
    dataset_path = tmp_path / 'golden_dataset.jsonl'
    write_rows(
        dataset_path,
        [
            {
                'id': 1,
                'category': 'Existing',
                'question': 'Existing question?',
                'expected': {'answerable': False, 'reference_answer': None},
            }
        ],
    )
    actions = iter(['Create new question', 'Save and quit'])
    text_answers = iter(
        [
            'Transport',
            'How do I reach Dinan?',
            'Take the regional train.',
            'https://example.test/guide.pdf',
            '2026',
            'Guide > Transport',
        ]
    )
    monkeypatch.setattr(
        annotator.questionary,
        'select',
        lambda *_args, **_kwargs: _Prompt(next(actions)),
    )
    monkeypatch.setattr(
        annotator.questionary,
        'text',
        lambda *_args, **_kwargs: _Prompt(next(text_answers)),
    )
    monkeypatch.setattr(
        annotator.questionary,
        'confirm',
        lambda *_args, **_kwargs: _Prompt(True),
    )

    annotator.annotate(
        load_rows(dataset_path), dataset_path, start_id=None, resume=False
    )

    rows = load_rows(dataset_path)
    assert rows[-1]['id'] == 2
    assert rows[-1]['expected']['reference_answer'] == 'Take the regional train.'
    assert rows[-1]['expected']['relevant_source']['section_path'] == [
        'guide',
        'transport',
    ]


def test_find_next_unanswered_uses_missing_current_format_annotations() -> None:
    """Verify that resume finds incomplete answerable rows without legacy markers."""
    rows = [
        {
            'expected': {
                'answerable': True,
                'reference_answer': 'Done',
                'relevant_source': {'section_path': ['guide']},
            }
        },
        {
            'expected': {
                'answerable': True,
                'reference_answer': None,
                'relevant_source': {'section_path': ['guide']},
            }
        },
        {'expected': {'answerable': False, 'reference_answer': None}},
    ]

    assert find_next_unanswered(rows) == 1
    assert find_next_unanswered(rows, start_index=3) is None


def test_initial_and_next_index_respect_resume_mode() -> None:
    """Verify that initial and next index respect resume mode."""
    rows = [
        {
            'id': 1,
            'expected': {
                'answerable': True,
                'reference_answer': 'Done',
                'relevant_source': {'section_path': ['guide']},
            },
        },
        {
            'id': 2,
            'expected': {
                'answerable': True,
                'reference_answer': None,
                'relevant_source': {'section_path': ['guide']},
            },
        },
        {
            'id': 3,
            'expected': {
                'answerable': True,
                'reference_answer': None,
                'relevant_source': {'section_path': ['guide']},
            },
        },
    ]

    assert initial_index(rows, start_id=None, resume=False) == 0
    assert initial_index(rows, start_id=None, resume=True) == 1
    assert initial_index(rows, start_id=3, resume=True) == 2
    assert next_index(rows, index=0, resume=False) == 1
    assert next_index(rows, index=1, resume=True) == 2
