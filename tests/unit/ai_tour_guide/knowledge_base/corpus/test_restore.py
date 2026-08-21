"""Tests for corpus restore and clearing."""

from unittest.mock import MagicMock, patch

import pytest

from ai_tour_guide.knowledge_base.corpus.format import CORPUS_FILES
from ai_tour_guide.knowledge_base.corpus.restore import (
    _INSERT_DOCUMENT_CHUNKS,
    clear_knowledge_base,
    load_corpus,
)


def _corpus_root(tmp_path):
    for name in CORPUS_FILES:
        (tmp_path / name).write_text('{"row": 1}\n', encoding='utf-8')
    return tmp_path


def _engine_with_cursor() -> MagicMock:
    engine = MagicMock()
    raw_connection = engine.raw_connection.return_value
    cursor = raw_connection.cursor.return_value
    cursor.copy.return_value.__enter__.return_value.write = MagicMock()
    return engine


@patch('ai_tour_guide.knowledge_base.corpus.restore.initialize_database')
def test_load_corpus_uses_database_initializer_as_single_ddl_source(
    initialize_database: MagicMock, tmp_path
) -> None:
    """Verify that restore delegates schema creation to the database initializer."""
    root = _corpus_root(tmp_path)
    engine = _engine_with_cursor()

    assert load_corpus(root=root, engine=engine, schema_name='evaluation') == root

    initialize_database.assert_called_once_with('evaluation', engine=engine)


def test_load_corpus_restores_section_metadata_and_embeddings(tmp_path) -> None:
    """Verify that chunk restore SQL consumes section metadata and vector values."""
    root = _corpus_root(tmp_path)
    engine = _engine_with_cursor()

    load_corpus(root=root, engine=engine, initialize_schema=False)

    cursor = engine.raw_connection.return_value.cursor.return_value
    executed_sql = '\n'.join(
        str(call.args[0]) for call in cursor.execute.call_args_list
    )
    assert _INSERT_DOCUMENT_CHUNKS.strip() in executed_sql
    assert 'section_id' in _INSERT_DOCUMENT_CHUNKS
    assert 'section_chunk_index' in _INSERT_DOCUMENT_CHUNKS
    assert '::vector' in _INSERT_DOCUMENT_CHUNKS
    assert engine.raw_connection.return_value.commit.called


def test_load_corpus_rolls_back_on_failure(tmp_path) -> None:
    """Verify that a failed COPY/import transaction is rolled back and closed."""
    root = _corpus_root(tmp_path)
    engine = _engine_with_cursor()
    cursor = engine.raw_connection.return_value.cursor.return_value
    cursor.execute.side_effect = RuntimeError('database write failed')

    with pytest.raises(RuntimeError, match='database write failed'):
        load_corpus(root=root, engine=engine, initialize_schema=False)

    raw_connection = engine.raw_connection.return_value
    raw_connection.rollback.assert_called_once_with()
    raw_connection.close.assert_called_once_with()


def test_clear_knowledge_base_truncates_without_dropping_tables() -> None:
    """Verify that clearing rows preserves the initialized schema and tables."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    clear_knowledge_base(engine=engine, schema_name='smoke')

    statement = connection.exec_driver_sql.call_args.args[0]
    assert statement.startswith('TRUNCATE TABLE')
    assert 'RESTART IDENTITY' in statement
    assert 'DROP' not in statement
