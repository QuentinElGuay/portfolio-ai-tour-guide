"""Tests for SQLAlchemy engine creation and schema selection."""

from unittest.mock import MagicMock, patch

from ai_tour_guide.knowledge_base.database.connection import database_engine


@patch('ai_tour_guide.knowledge_base.database.connection.create_database_engine')
@patch('ai_tour_guide.knowledge_base.database.connection.DatabaseSettings')
def test_database_engine_uses_environment_selected_schema_by_default(
    database_settings: MagicMock,
    create_database_engine: MagicMock,
) -> None:
    settings = database_settings.return_value
    engine = create_database_engine.return_value

    with database_engine() as selected_engine:
        assert selected_engine is engine

    database_settings.assert_called_once_with()
    create_database_engine.assert_called_once_with(settings)
    engine.dispose.assert_called_once_with()


@patch('ai_tour_guide.knowledge_base.database.connection.create_database_engine')
@patch('ai_tour_guide.knowledge_base.database.connection.DatabaseSettings')
def test_database_engine_uses_an_explicit_schema_override(
    database_settings: MagicMock,
    create_database_engine: MagicMock,
) -> None:
    settings = database_settings.return_value

    with database_engine(schema_name='smoke'):
        pass

    database_settings.assert_called_once_with(schema_name='smoke')
    create_database_engine.assert_called_once_with(settings)
