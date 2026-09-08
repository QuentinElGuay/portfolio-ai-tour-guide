"""Read the destination catalog represented by indexed documents."""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.models import DocumentRow


def list_indexed_destinations(engine: Engine | None = None) -> tuple[str, ...]:
    """Return indexed destination names in a stable order for the assistant catalog."""
    statement = select(DocumentRow.destination).order_by(DocumentRow.destination)

    with database_engine(engine) as db_engine, Session(db_engine) as session:
        return tuple(session.scalars(statement).all())


def has_indexed_documents(engine: Engine | None = None) -> bool:
    """Return whether the active knowledge base contains at least one document."""
    statement = select(DocumentRow.document_id).limit(1)

    with database_engine(engine) as db_engine, Session(db_engine) as session:
        return session.scalar(statement) is not None


__all__ = ['has_indexed_documents', 'list_indexed_destinations']
