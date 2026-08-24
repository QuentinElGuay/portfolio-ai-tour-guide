from datetime import UTC, datetime

import pytest

from ai_tour_guide.domain.documents import DocumentMetadata
from ai_tour_guide.ingestion.pdf.parser import _parse_pdf_metadata_datetime


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (
            "D:20260102030405+02'30'",
            datetime(2026, 1, 2, 0, 34, 5, tzinfo=UTC),
        ),
        (
            'D:20260102030405Z',
            datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        ),
        (
            '2026-01-02T03:04:05-03:00',
            datetime(2026, 1, 2, 6, 4, 5, tzinfo=UTC),
        ),
    ],
)
def test_parse_pdf_metadata_datetime_normalizes_to_utc(
    value: str,
    expected: datetime,
) -> None:
    """Verify that parse pdf metadata datetime normalizes to utc."""
    assert _parse_pdf_metadata_datetime(value) == expected


@pytest.mark.parametrize(
    'value',
    [
        None,
        '',
        'D:20260102030405',
        'D:20261302030405Z',
        "D:20260102030405+25'00'",
        'not-a-date',
    ],
)
def test_parse_pdf_metadata_datetime_rejects_unreliable_values(
    value: str | None,
) -> None:
    """Verify that parse pdf metadata datetime rejects unreliable values."""
    assert _parse_pdf_metadata_datetime(value) is None


def test_document_metadata_rejects_naive_timestamps() -> None:
    """Verify that document metadata rejects naive timestamps."""
    with pytest.raises(
        ValueError,
        match='creation_date must include timezone information',
    ):
        DocumentMetadata(
            title='Guide',
            source_url='https://example.com/guide.pdf',
            publisher=None,
            publication_date=None,
            authors=(),
            subject=None,
            keywords=(),
            creator=None,
            producer=None,
            format='PDF 1.7',
            creation_date=datetime(2026, 1, 2),  # noqa: DTZ001 - invalid by design
            modification_date=None,
            source_page_count=1,
            page_count=1,
        )
