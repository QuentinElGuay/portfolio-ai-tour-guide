"""Runtime configuration shared by the application entry points."""

import logging
import os

APP_DEBUG_ENVIRONMENT_VARIABLE = 'APP_DEBUG'
DEFAULT_APP_DEBUG = False


def app_debug_enabled() -> bool:
    """Return whether application debug diagnostics are enabled."""
    value = os.getenv(APP_DEBUG_ENVIRONMENT_VARIABLE, str(DEFAULT_APP_DEBUG))
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def configure_application_logging() -> None:
    """Configure application logging from the APP_DEBUG runtime setting."""
    level = logging.DEBUG if app_debug_enabled() else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    logging.getLogger().setLevel(level)


__all__ = [
    'APP_DEBUG_ENVIRONMENT_VARIABLE',
    'DEFAULT_APP_DEBUG',
    'app_debug_enabled',
    'configure_application_logging',
]
