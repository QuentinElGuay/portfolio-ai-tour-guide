from sqlalchemy import text
from sqlalchemy.schema import CreateSchema

from ai_tour_guide.knowledge_base.connection import create_database_engine
from ai_tour_guide.knowledge_base.settings import DatabaseSettings
from ai_tour_guide.knowledge_base.tables import metadata


def initialize_database() -> None:
    """Enable pgvector and create the application tables."""

    settings = DatabaseSettings()
    engine = create_database_engine(settings)

    with engine.begin() as connection:
        connection.execute(
            text('CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public')
        )
        connection.execute(CreateSchema(settings.schema_name, if_not_exists=True))

        metadata.create_all(
            bind=connection,
            checkfirst=True,
        )
        for table in metadata.tables.values():
            for index in table.indexes:
                index.create(bind=connection, checkfirst=True)

    engine.dispose()


def main() -> None:
    initialize_database()
    print('Database initialized successfully.')


if __name__ == '__main__':
    main()
