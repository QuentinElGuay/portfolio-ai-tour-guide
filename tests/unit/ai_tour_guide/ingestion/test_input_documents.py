import json
from io import StringIO

import pytest

from ai_tour_guide.ingestion.cli import load_documents


def test_collection_is_loaded_from_the_documents_input() -> None:
    """Verify that collection is loaded from the documents input."""
    documents = load_documents(
        StringIO(
            '{'
            '"title": "A guide to Brittany",'
            '"source_url": "https://example.com/brittany",'
            '"collection": "  tour-guides  "'
            '}'
        )
    )

    assert documents[0].collection == 'tour-guides'


def test_collection_is_optional_in_the_documents_input() -> None:
    """Verify that collection is optional in the documents input."""
    documents = load_documents(
        StringIO(
            '{'
            '"title": "A guide to Brittany",'
            '"source_url": "https://example.com/brittany"'
            '}'
        )
    )

    assert documents[0].collection is None


def test_local_source_path_is_loaded_and_becomes_a_file_source_url(tmp_path) -> None:
    source_path = tmp_path / 'brittany.pdf'
    documents = load_documents(
        StringIO(
            json.dumps(
                {'title': 'A guide to Brittany', 'source_path': str(source_path)}
            )
        )
    )

    assert documents[0].source_path == source_path.resolve()
    assert documents[0].source_url == source_path.resolve().as_uri()


@pytest.mark.parametrize('collection', ['', '   ', 123])
def test_collection_rejects_empty_and_non_string_values(
    collection: str | int,
) -> None:
    """Verify that collection rejects empty and non string values."""
    source = StringIO(
        json.dumps(
            {
                'title': 'A guide to Brittany',
                'source_url': 'https://example.com/brittany',
                'collection': collection,
            }
        )
    )

    with pytest.raises(ValueError, match='collection'):
        load_documents(source)
