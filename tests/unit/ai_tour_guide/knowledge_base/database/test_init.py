"""Tests for schema initialization orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from ai_tour_guide.knowledge_base.database import init


def test_initialize_database_creates_extension_schema_tables_and_indexes() -> None:
    """Verify that initialization creates extension/schema before Core metadata."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    schema_connection = connection.execution_options.return_value
    index = MagicMock()
    table = MagicMock(indexes={index})

    with (
        patch.object(init, 'public_metadata') as metadata,
        patch.object(init, '_migrate_llm_model_pricing'),
        patch.object(init, '_migrate_llm_usage_events'),
        patch.object(init, '_seed_default_llm_model_pricing'),
    ):
        metadata.tables = {'document_chunks': table}
        init.initialize_database('smoke', engine=engine)

    assert connection.execute.call_count == 2
    connection.execution_options.assert_called_once_with(
        schema_translate_map={None: 'smoke'}
    )
    metadata.create_all.assert_called_once_with(bind=schema_connection, checkfirst=True)
    index.create.assert_called_once_with(bind=schema_connection, checkfirst=True)


def test_initialize_database_rejects_unsupported_schema() -> None:
    """Verify that unsupported schemas fail before any database work begins."""
    with pytest.raises(ValueError, match='Unsupported schema'):
        init.initialize_database('unsafe')


@patch('ai_tour_guide.knowledge_base.database.init.database_engine')
def test_initialize_database_delegates_engine_ownership_to_database_context(
    database_engine: MagicMock,
) -> None:
    """Verify that initialization passes caller-owned engines to the shared context."""
    engine = MagicMock()
    db_engine = database_engine.return_value.__enter__.return_value
    connection = db_engine.begin.return_value.__enter__.return_value
    connection.execution_options.return_value = MagicMock()

    with (
        patch.object(init.public_metadata, 'create_all'),
        patch.object(init.public_metadata, 'tables', {}),
    ):
        init.initialize_database('evaluation', engine=engine)

    database_engine.assert_called_once_with(engine, schema_name='evaluation')
