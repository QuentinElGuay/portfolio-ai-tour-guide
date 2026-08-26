"""Read the destination catalog represented by indexed documents."""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentRow


def list_known_destination_titles(engine: Engine | None = None) -> tuple[str, ...]:
    """Return indexed guide titles in a stable order for the assistant catalog."""
    statement = select(DocumentRow.title).order_by(DocumentRow.title)

    with database_engine(engine) as db_engine, Session(db_engine) as session:
        return tuple(session.scalars(statement).all())


__all__ = ['list_known_destination_titles']
