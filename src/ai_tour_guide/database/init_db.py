from __future__ import annotations

from sqlalchemy import text

from ai_tour_guide.database.connection import create_database_engine
from ai_tour_guide.database.tables import metadata


def initialize_database() -> None:
    """Enable pgvector and create the application tables."""

    engine = create_database_engine()

    with engine.begin() as connection:
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))

        metadata.create_all(
            bind=connection,
            checkfirst=True,
        )

    engine.dispose()


def main() -> None:
    initialize_database()
    print('Database initialized successfully.')


if __name__ == '__main__':
    main()
