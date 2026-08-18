import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from ai_tour_guide.embedding import Embedder
from ai_tour_guide.ingestion import pipeline
from ai_tour_guide.ingestion.cli import main
from ai_tour_guide.ingestion.config import ChunkingConfig
from ai_tour_guide.ingestion.pdf.parser import IngestionDocument
from ai_tour_guide.ingestion.settings import IngestionSettings


def test_cli_exposes_each_stage_and_the_pipeline() -> None:
    result = CliRunner().invoke(main, ['--help'])

    assert result.exit_code == 0
    assert {'download', 'parse', 'chunk', 'embed', 'load', 'run'} <= set(
        result.output.split()
    )


def test_individual_document_command_rejects_an_array(tmp_path: Path) -> None:
    input_path = tmp_path / 'documents.json'
    input_path.write_text(
        json.dumps(
            [
                {
                    'title': 'First guide',
                    'source_url': 'https://example.test/first.pdf',
                },
                {
                    'title': 'Second guide',
                    'source_url': 'https://example.test/second.pdf',
                },
            ]
        ),
        encoding='utf-8',
    )

    result = CliRunner().invoke(
        main,
        ['download', str(input_path), '--output', str(tmp_path / 'guide.pdf')],
    )

    assert result.exit_code == 1
    assert 'exactly one document' in result.output


@pytest.mark.parametrize('debug', [False, True])
def test_document_pipeline_retains_artifacts_only_in_debug_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    debug: bool,
) -> None:
    document = IngestionDocument(
        title='Test guide',
        source_url='https://example.test/guide.pdf',
    )
    downloaded = object()
    parsed = object()
    chunked = object()
    embedded = object()
    embedder: Embedder = MagicMock(spec=Embedder)

    download_stage = MagicMock(return_value=downloaded)
    parse_stage = MagicMock(return_value=parsed)
    chunk_stage = MagicMock(return_value=chunked)
    embed_stage = MagicMock(return_value=embedded)
    load_stage = MagicMock(return_value=42)
    write_debug_artifacts = MagicMock()

    monkeypatch.setattr(pipeline, 'download_pdf_stage', download_stage)
    monkeypatch.setattr(pipeline, 'parse_pdf_stage', parse_stage)
    monkeypatch.setattr(pipeline, 'chunk_document_stage', chunk_stage)
    monkeypatch.setattr(pipeline, 'embed_document_stage', embed_stage)
    monkeypatch.setattr(pipeline, 'load_document_stage', load_stage)
    monkeypatch.setattr(
        pipeline,
        '_write_debug_artifacts',
        write_debug_artifacts,
    )

    artifact_directory = tmp_path / 'artifacts'
    result = pipeline.run_document_pipeline(
        document,
        settings=IngestionSettings(
            tmp_folder=artifact_directory,
            timeout=30.0,
            debug=debug,
        ),
        embedder=embedder,
        embedding_batch_size=8,
        chunking_config=ChunkingConfig(500, 700, 1, 2),
    )

    assert result == 42
    download_stage.assert_called_once_with(document, timeout_seconds=30.0)
    parse_stage.assert_called_once_with(downloaded)
    chunk_stage.assert_called_once_with(
        parsed,
        config=ChunkingConfig(500, 700, 1, 2),
    )
    embed_stage.assert_called_once_with(
        chunked,
        embedder=embedder,
        batch_size=8,
    )
    load_stage.assert_called_once_with(embedded)

    if debug:
        write_debug_artifacts.assert_called_once_with(
            artifact_directory,
            downloaded,
            parsed,
            chunked,
            embedded,
        )
    else:
        write_debug_artifacts.assert_not_called()
        assert not artifact_directory.exists()
