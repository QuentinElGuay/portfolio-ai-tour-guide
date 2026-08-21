"""Fixtures for an isolated, end-to-end ingestion and RAG smoke test."""

import json
import os
from collections.abc import Iterator
from datetime import date

import pytest

from ai_tour_guide.embedding import FastEmbedder
from ai_tour_guide.embedding.settings import EmbeddingSettings
from ai_tour_guide.ingestion.pdf.parser import IngestionDocument
from ai_tour_guide.ingestion.pipeline import run_pipeline
from ai_tour_guide.ingestion.settings import IngestionSettings
from ai_tour_guide.knowledge_base.corpus import clear_knowledge_base
from ai_tour_guide.knowledge_base.database.settings import DatabaseSettings

from .pdf_fixture import create_brittany_weekend_notes


@pytest.fixture(scope='session', autouse=True)
def ingested_smoke_document(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Generate and ingest the original local PDF before API smoke checks."""
    assert DatabaseSettings().schema_name == 'smoke'
    fixture_directory = tmp_path_factory.mktemp('smoke-pdf')
    pdf_path = create_brittany_weekend_notes(
        fixture_directory / 'brittany-weekend-notes.pdf'
    )
    source_url = 'https://smoke.test/brittany-weekend-notes.pdf'
    dataset_path = fixture_directory / 'golden_dataset.jsonl'
    dataset_path.write_text(
        json.dumps(
            {
                'id': 1,
                'category': 'Smoke-test travel',
                'question': 'How can visitors travel from Rennes to Saint-Malo?',
                'expected': {
                    'answerable': True,
                    'reference_answer': (
                        'Visitors can take the regional train from Rennes to '
                        'Saint-Malo; the journey usually takes about fifty minutes.'
                    ),
                    'relevant_source': {
                        'source_url': source_url,
                        'version': None,
                        'section_path': [
                            'brittany-weekend-notes',
                            'getting-around-brittany',
                        ],
                    },
                },
            }
        )
        + '\n'
        + json.dumps(
            {
                'id': 2,
                'category': 'Smoke-test unsupported',
                'question': 'Can you reserve a hotel in Saint-Malo tonight?',
                'expected': {'answerable': False, 'reference_answer': None},
            }
        )
        + '\n',
        encoding='utf-8',
    )
    previous_dataset = os.environ.get('AGENT_LLM_FIXTURE_DATASET')
    os.environ['AGENT_LLM_FIXTURE_DATASET'] = str(dataset_path)

    clear_knowledge_base(schema_name='smoke')
    settings = IngestionSettings(timeout=10)
    embedding_settings = EmbeddingSettings()
    try:
        run_pipeline(
            (
                IngestionDocument(
                    title='Brittany Weekend Notes',
                    source_url=source_url,
                    source_path=pdf_path,
                    collection='Smoke Test Guides',
                    publisher='Smoke Test Press',
                    publication_date=date(2026, 8, 21),
                    excluded_leading_pages=1,
                    excluded_trailing_pages=0,
                ),
            ),
            settings=settings,
            embedder=FastEmbedder(
                model_name=embedding_settings.model_name,
                normalize=embedding_settings.normalize,
                cache_dir=embedding_settings.cache_dir,
            ),
            embedding_batch_size=embedding_settings.batch_size,
            chunking_config=settings.chunking_config,
        )
        yield
    finally:
        if previous_dataset is None:
            os.environ.pop('AGENT_LLM_FIXTURE_DATASET', None)
        else:
            os.environ['AGENT_LLM_FIXTURE_DATASET'] = previous_dataset
        clear_knowledge_base(schema_name='smoke')
