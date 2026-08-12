from sqlalchemy import URL, Engine, create_engine

from ai_tour_guide.knowledge_base.settings import DatabaseSettings


def _search_path_option(schema: str) -> str:
    return f'-csearch_path={schema},public'


def create_database_engine(settings: DatabaseSettings | None = None) -> Engine:
    """Create the PostgreSQL SQLAlchemy engine."""
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
