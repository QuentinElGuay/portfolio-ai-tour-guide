"""Tests for database settings validation."""

import pytest
from pydantic import SecretStr, ValidationError

from ai_tour_guide.knowledge_base.database.settings import DatabaseSettings


def test_database_settings_loads_db_environment_variables(monkeypatch) -> None:
    """Verify that database settings read and type-check DB environment values."""
    monkeypatch.setenv('DB_USER', 'guide')
    monkeypatch.setenv('DB_PASSWORD', 'secret')
    monkeypatch.setenv('DB_NAME', 'tour-guide')
    monkeypatch.setenv('DB_HOST', 'database')
    monkeypatch.setenv('DB_PORT', '5433')
    monkeypatch.setenv('DB_SCHEMA', 'evaluation')

    settings = DatabaseSettings()

    assert settings.user == 'guide'
    assert settings.password.get_secret_value() == 'secret'
    assert settings.host == 'database'
    assert settings.port == 5433
    assert settings.name == 'tour-guide'
    assert settings.schema_name == 'evaluation'


def test_database_settings_rejects_invalid_schema_identifier() -> None:
    """Verify that unsafe schema names are rejected before connection creation."""
    with pytest.raises(ValidationError, match='schema_name'):
        DatabaseSettings(
            user='guide',
            password=SecretStr('secret'),
            name='tour-guide',
            schema_name='bad-name',
        )
