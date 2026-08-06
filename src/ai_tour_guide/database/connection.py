
import os

from sqlalchemy import URL, Engine, create_engine


def create_database_engine() -> Engine:
    """Create the PostgreSQL SQLAlchemy engine."""

    database_url = URL.create(
        drivername='postgresql+psycopg',
        username=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        host=os.environ['DB_HOST'],
        port=int(os.environ['DB_PORT']),
        database=os.environ['DB_NAME'],
    )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )
