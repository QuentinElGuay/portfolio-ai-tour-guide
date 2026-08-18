"""SQLAlchemy engine creation for the knowledge-base database."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import URL, Engine, create_engine

from .settings import DatabaseSettings


def _search_path_option(schema: str) -> str:
    return f'-csearch_path={schema},public'


def create_database_engine(settings: DatabaseSettings | None = None) -> Engine:
    """Create a PostgreSQL SQLAlchemy engine using the selected schema search path."""
    selected_settings = settings or DatabaseSettings()
    database_url = URL.create(
        drivername='postgresql+psycopg',
        username=selected_settings.user,
        password=selected_settings.password.get_secret_value(),
        host=selected_settings.host,
        port=selected_settings.port,
        database=selected_settings.name,
    )
    return create_engine(
        database_url,
        connect_args={'options': _search_path_option(selected_settings.schema_name)},
        pool_pre_ping=True,
    )


@contextmanager
def database_engine(
    engine: Engine | None = None, *, schema_name: str = 'public'
) -> Iterator[Engine]:
    """Yield an engine and dispose it only when this context creates it."""
    owned_engine = engine is None
    db_engine = engine or create_database_engine(
        DatabaseSettings(schema_name=schema_name)
    )
    try:
        yield db_engine
    finally:
        if owned_engine:
            db_engine.dispose()


__all__ = ['create_database_engine', 'database_engine']
