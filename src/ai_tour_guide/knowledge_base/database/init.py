"""Database/schema initialization using the Core metadata as the single DDL source."""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateSchema

from .connection import database_engine
from .settings import DatabaseSettings
from .tables import metadata

SUPPORTED_SCHEMA_NAMES = ('public', 'test', 'evaluation')


def initialize_database(
    schema_name: str = 'public', *, engine: Engine | None = None
) -> None:
    """Enable pgvector and create all knowledge-base tables in ``schema_name``."""
    if schema_name not in SUPPORTED_SCHEMA_NAMES:
        choices = ', '.join(SUPPORTED_SCHEMA_NAMES)
        raise ValueError(
            f'Unsupported schema {schema_name!r}; choose one of: {choices}'
        )

    with (
        database_engine(engine, schema_name=schema_name) as db_engine,
        db_engine.begin() as connection,
    ):
        connection.execute(
            text('CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public')
        )
        connection.execute(CreateSchema(schema_name, if_not_exists=True))
        schema_connection = connection.execution_options(
            schema_translate_map={None: schema_name}
        )
        metadata.create_all(bind=schema_connection, checkfirst=True)
        for table in metadata.tables.values():
            for index in table.indexes:
                index.create(bind=schema_connection, checkfirst=True)


def main() -> None:
    """CLI entry point for initializing the configured knowledge-base schema."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Initialize the knowledge-base schema.'
    )
    parser.add_argument('--schema', choices=SUPPORTED_SCHEMA_NAMES)
    args = parser.parse_args()
    initialize_database(args.schema or DatabaseSettings().schema_name)
    print('Database initialized successfully.')


if __name__ == '__main__':
    main()


__all__ = ['SUPPORTED_SCHEMA_NAMES', 'initialize_database']
