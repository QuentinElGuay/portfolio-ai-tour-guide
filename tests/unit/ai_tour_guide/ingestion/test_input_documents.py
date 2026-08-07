import json
import os
from io import StringIO

import pytest

os.environ.setdefault('EMBEDDING_DIMENSIONS', '384')

from ai_tour_guide.ingestion.cli import load_documents


def test_collection_is_loaded_from_the_documents_input() -> None:
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
    documents = load_documents(
        StringIO(
            '{'
            '"title": "A guide to Brittany",'
            '"source_url": "https://example.com/brittany"'
            '}'
        )
    )

    assert documents[0].collection is None


@pytest.mark.parametrize('collection', ['', '   ', 123])
def test_collection_rejects_empty_and_non_string_values(
    collection: str | int,
) -> None:
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
