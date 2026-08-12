from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from ai_tour_guide.knowledge_base.connection import create_database_engine
from ai_tour_guide.knowledge_base.settings import DatabaseSettings


def test_database_settings_defaults_to_public_schema() -> None:
    settings = DatabaseSettings(
        user='postgres',
        password=SecretStr('postgres'),
        name='postgres',
    )

    assert settings.schema_name == 'public'


def test_database_settings_loads_schema_from_environment(monkeypatch) -> None:
    monkeypatch.setenv('DB_SCHEMA', 'evaluation')

    settings = DatabaseSettings(
        user='postgres',
        password=SecretStr('postgres'),
        name='postgres',
    )

    assert settings.schema_name == 'evaluation'


def test_database_settings_rejects_unsafe_schema_names() -> None:
    with pytest.raises(ValidationError):
        DatabaseSettings(
            user='postgres',
            password=SecretStr('postgres'),
            name='postgres',
            schema_name='evaluation;drop schema public',
        )


@patch('ai_tour_guide.knowledge_base.connection.create_engine')
def test_create_database_engine_sets_schema_search_path(create_engine) -> None:
    settings = DatabaseSettings(
        user='postgres',
        password=SecretStr('postgres'),
        name='postgres',
        schema_name='evaluation',
    )

    create_database_engine(settings)

    assert create_engine.call_args.kwargs['connect_args'] == {
        'options': '-csearch_path=evaluation,public',
    }
