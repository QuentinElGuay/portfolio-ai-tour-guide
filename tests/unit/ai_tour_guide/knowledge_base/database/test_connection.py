"""Tests for SQLAlchemy engine creation and schema selection."""

from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from ai_tour_guide.knowledge_base.database.connection import (
    create_database_engine,
    database_engine,
)
from ai_tour_guide.knowledge_base.database.settings import DatabaseSettings

@patch('ai_tour_guide.knowledge_base.database.connection.create_database_engine')
@patch('ai_tour_guide.knowledge_base.database.connection.DatabaseSettings')
def test_database_engine_uses_environment_selected_schema_by_default(
    database_settings: MagicMock,
    create_database_engine: MagicMock,
) -> None:
    settings = database_settings.return_value
    engine = create_database_engine.return_value

@patch('ai_tour_guide.knowledge_base.database.connection.create_engine')
def test_create_database_engine_builds_expected_postgres_url(
    create_engine: MagicMock,
) -> None:
    """Verify that engine creation applies credentials and schema search path."""
    settings = DatabaseSettings(
        user='guide',
        password=SecretStr('secret'),
        host='db',
        port=5433,
        name='tour-guide',
        schema_name='evaluation',
    )

    create_database_engine(settings)

    url = create_engine.call_args.args[0]
    assert url.drivername == 'postgresql+psycopg'
    assert url.username == 'guide'
    assert url.host == 'db'
    assert url.port == 5433
    assert create_engine.call_args.kwargs == {
        'connect_args': {'options': '-csearch_path=evaluation,public'},
        'pool_pre_ping': True,
    }


@patch('ai_tour_guide.knowledge_base.database.connection.create_database_engine')
@patch('ai_tour_guide.knowledge_base.database.connection.DatabaseSettings')
def test_database_engine_uses_environment_selected_schema_by_default(
    database_settings: MagicMock,
    create_database_engine: MagicMock,
) -> None:
    """Verify that a created engine uses the default environment settings."""
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
    """Verify that a caller can override the selected schema."""
    settings = database_settings.return_value

    with database_engine(schema_name='smoke'):
        pass

    database_settings.assert_called_once_with(schema_name='smoke')
    create_database_engine.assert_called_once_with(settings)


@patch('ai_tour_guide.knowledge_base.database.connection.create_database_engine')
def test_database_engine_disposes_only_an_owned_engine(
    create_database_engine: MagicMock,
) -> None:
    """Verify that the context manager disposes only engines it creates."""
    owned = create_database_engine.return_value
    injected = MagicMock()

    with database_engine() as selected:
        assert selected is owned
    with database_engine(injected) as selected:
        assert selected is injected

    owned.dispose.assert_called_once_with()
    injected.dispose.assert_not_called()
