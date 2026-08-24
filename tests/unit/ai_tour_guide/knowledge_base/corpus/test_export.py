"""Tests for corpus export."""

from unittest.mock import MagicMock, patch

from ai_tour_guide.knowledge_base.corpus.export import _EXPORTS, export_corpus
from ai_tour_guide.knowledge_base.corpus.format import CORPUS_FILES


def _engine_with_copy_rows(*rows: bytes) -> MagicMock:
    engine = MagicMock()
    raw_connection = engine.raw_connection.return_value
    cursor = raw_connection.cursor.return_value
    copy = cursor.copy.return_value.__enter__.return_value
    copy.__iter__.side_effect = lambda: iter(rows)
    return engine


def test_export_corpus_writes_all_logical_files(tmp_path) -> None:
    """Verify that every logical corpus file is exported through COPY streams."""
    engine = _engine_with_copy_rows(b'{"id": 1}\n')

    result = export_corpus(root=tmp_path, engine=engine)

    assert result == tmp_path
    assert {path.name for path in tmp_path.iterdir()} == set(CORPUS_FILES)
    assert all(
        (tmp_path / name).read_bytes() == b'{"id": 1}\n' for name in CORPUS_FILES
    )
    assert (
        engine.raw_connection.return_value.cursor.return_value.copy.call_count
        == len(CORPUS_FILES)
    )
    assert 'search_vector' not in _EXPORTS['document_chunks.jsonl']
    assert 'embedding' in _EXPORTS['document_chunks.jsonl']
    assert 'section_chunk_index' in _EXPORTS['document_chunks.jsonl']


@patch('ai_tour_guide.knowledge_base.corpus.export.database_engine')
def test_export_corpus_uses_the_shared_database_context(
    database_engine: MagicMock, tmp_path
) -> None:
    """Verify that export delegates owned-versus-injected cleanup to the DB context."""
    engine = MagicMock()
    db_engine = database_engine.return_value.__enter__.return_value
    copy = db_engine.raw_connection.return_value.cursor.return_value.copy.return_value
    copy.__enter__.return_value.__iter__.return_value = iter(())

    export_corpus(root=tmp_path, engine=engine)

    database_engine.assert_called_once_with(engine)
    assert db_engine.raw_connection.return_value.close.called
