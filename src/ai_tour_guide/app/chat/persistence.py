"""Persistence for provider-neutral conversation messages and feedback."""

from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from ai_tour_guide.app.chat.models import ChatMessage
from ai_tour_guide.knowledge_base.database.connection import database_engine
from ai_tour_guide.knowledge_base.database.tables.public import (
    chat_feedback,
    chat_messages,
)


def store_chat_message(message: ChatMessage, *, engine: Engine | None = None) -> None:
    """Store one immutable conversation message."""
    with database_engine(engine) as db_engine, db_engine.begin() as connection:
        connection.execute(
            insert(chat_messages).values(
                message_id=message.message_id,
                session_id=message.session_id,
                role=message.role.value,
                content=message.content,
                flow_step=message.flow_step,
                input_id=message.input_id,
                rag_request_id=message.rag_request_id,
                sources=message.sources,
                trace=(
                    message.trace.model_dump(mode='json') if message.trace else None
                ),
                buttons=[button.model_dump(mode='json') for button in message.buttons],
            )
        )


def store_feedback(
    message_id: UUID,
    helpful: bool,
    comment: str | None = None,
    *,
    engine: Engine | None = None,
) -> bool:
    """Store feedback for an existing assistant message."""
    with database_engine(engine) as db_engine, db_engine.begin() as connection:
        exists = connection.scalar(
            select(chat_messages.c.message_id)
            .where(chat_messages.c.message_id == message_id)
            .limit(1)
        )
        if exists is None:
            return False
        connection.execute(
            insert(chat_feedback).values(
                message_id=message_id,
                helpful=helpful,
                comment=comment,
            )
        )
    return True


__all__ = ['store_chat_message', 'store_feedback']
