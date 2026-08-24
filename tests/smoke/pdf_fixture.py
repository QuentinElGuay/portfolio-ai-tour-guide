"""Original PDF content used to exercise the ingestion smoke test."""

from pathlib import Path

import pymupdf


def create_brittany_weekend_notes(path: Path) -> Path:
    """Create a small guide with the typography and hierarchy ingestion expects."""
    document = pymupdf.open()
    _cover_page(document)
    _travel_page(document)
    _coast_page(document)
    document.set_metadata(
        {
            'title': 'Brittany Weekend Notes',
            'author': 'Smoke Test Press',
            'subject': 'Original local PDF fixture',
            'keywords': 'Brittany, travel, smoke test',
        }
    )
    document.save(path)
    document.close()
    return path


def _cover_page(document: pymupdf.Document) -> None:
    page = document.new_page()
    page.insert_text((72, 130), 'Brittany Weekend Notes', fontsize=26, fontname='hebo')
    page.insert_text(
        (72, 170), 'A short original guide for curious travellers', fontsize=14
    )
    page.insert_text(
        (72, 710), 'Smoke Test Press · 2026', fontsize=10, color=(0.25, 0.25, 0.25)
    )


def _travel_page(document: pymupdf.Document) -> None:
    page = document.new_page()
    page.insert_text((72, 80), 'Getting around Brittany', fontsize=20, fontname='hebo')
    page.insert_text((72, 125), 'Rennes to Saint-Malo', fontsize=15, fontname='hebo')
    page.insert_textbox(
        pymupdf.Rect(72, 155, 523, 270),
        (
            'For a relaxed day trip, take the regional train from Rennes to '
            'Saint-Malo. The journey usually takes about fifty minutes and arrives '
            'close to the walled old town. Buy a return ticket before boarding when '
            'you want flexibility for an evening walk by the harbour.'
        ),
        fontsize=11,
        lineheight=1.45,
    )


def _coast_page(document: pymupdf.Document) -> None:
    page = document.new_page()
    page.insert_text((72, 80), 'Coastal walks', fontsize=20, fontname='hebo')
    page.insert_text((72, 125), 'Cap Fréhel', fontsize=15, fontname='hebo')
    page.insert_textbox(
        pymupdf.Rect(72, 155, 523, 270),
        (
            'Cap Fréhel offers a breezy clifftop walk with sea views and heathland. '
            'Bring water, wear sturdy shoes, and allow time to stop at the lighthouse '
            'before returning along the same marked path.'
        ),
        fontsize=11,
        lineheight=1.45,
    )


__all__ = ['create_brittany_weekend_notes']
