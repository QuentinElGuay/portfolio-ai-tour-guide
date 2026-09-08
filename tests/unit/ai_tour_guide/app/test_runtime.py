"""Tests for application runtime configuration."""

import logging

from ai_tour_guide.app.runtime import app_debug_enabled, configure_application_logging


def test_app_debug_defaults_to_false(monkeypatch) -> None:
    monkeypatch.delenv('APP_DEBUG', raising=False)

    assert app_debug_enabled() is False


def test_app_debug_enables_debug_logging(monkeypatch) -> None:
    monkeypatch.setenv('APP_DEBUG', 'true')

    configure_application_logging()

    assert app_debug_enabled() is True
    assert logging.getLogger().level == logging.DEBUG
