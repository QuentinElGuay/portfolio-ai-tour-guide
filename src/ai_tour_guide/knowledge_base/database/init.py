"""Database/schema initialization using the Core metadata as the single DDL source."""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateSchema

from .connection import create_database_engine
from .settings import DatabaseSettings
from .tables import metadata

SUPPORTED_SCHEMA_NAMES = ('public', 'test', 'evaluation')


def initialize_database(
    schema_name: str = 'public', *, engine: Engine | None = None
) -> None:
    """Enable pgvector and create all knowledge-base tables in ``schema_name``."""
    if schema_name not in SUPPORTED_SCHEMA_NAMES:
        choices = ', '.join(SUPPORTED_SCHEMA_NAMES)
        raise ValueError(f'Unsupported schema {schema_name!r}; choose one of: {choices}')

    owned_engine = engine is None
    if engine is None:
        engine = create_database_engine(DatabaseSettings(schema_name=schema_name))

    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public'))
            connection.execute(CreateSchema(schema_name, if_not_exists=True))
            metadata.create_all(bind=connection, checkfirst=True)
            for table in metadata.tables.values():
                for index in table.indexes:
                    index.create(bind=connection, checkfirst=True)
    finally:
        if owned_engine:
            engine.dispose()


def main() -> None:
    """CLI entry point for initializing the configured knowledge-base schema."""
    import argparse

    parser = argparse.ArgumentParser(description='Initialize the knowledge-base schema.')
    parser.add_argument('--schema', choices=SUPPORTED_SCHEMA_NAMES)
    args = parser.parse_args()
    initialize_database(args.schema or DatabaseSettings().schema_name)
    print('Database initialized successfully.')


if __name__ == '__main__':
    main()


__all__ = ['SUPPORTED_SCHEMA_NAMES', 'initialize_database']
