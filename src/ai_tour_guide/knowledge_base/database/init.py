"""Database/schema initialization using the Core metadata as the single DDL source."""

from decimal import Decimal

from sqlalchemy import insert, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateSchema

from .connection import database_engine
from .settings import DatabaseSettings
from .tables.evaluation import metadata as evaluation_metadata
from .tables.public import llm_model_pricing
from .tables.public import metadata as public_metadata
from .views import create_evaluation_views, create_operational_views

SUPPORTED_SCHEMA_NAMES = ('public', 'test', 'evaluation', 'smoke')

# OpenAI published prices for gpt-4.1-mini, expressed per token. Keep prices in
# the database so later pricing changes can be represented by a new effective
# row rather than rewriting historical cost calculations.
DEFAULT_LLM_MODEL_PRICING = {
    ('openai', 'gpt-4.1-mini'): {
        'input_cost_per_token': Decimal('0.0000004'),
        'cached_input_cost_per_token': Decimal('0.0000001'),
        'output_cost_per_token': Decimal('0.0000016'),
        'currency': 'USD',
    }
}


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
        connection.execute(CreateSchema(schema_name, if_not_exists=True))
        connection.execute(
            text('CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public')
        )
        schema_connection = connection.execution_options(
            schema_translate_map={None: schema_name}
        )
        public_metadata.create_all(bind=schema_connection, checkfirst=True)
        connection.execute(
            text('ALTER TABLE documents ADD COLUMN IF NOT EXISTS destination TEXT')
        )
        connection.execute(
            text('UPDATE documents SET destination = title WHERE destination IS NULL')
        )
        connection.execute(
            text('ALTER TABLE documents ALTER COLUMN destination SET NOT NULL')
        )
        _migrate_chat_messages(connection)
        _trim_rag_result_message_columns(connection)
        _migrate_llm_usage_events(connection)
        for table in public_metadata.tables.values():
            for index in table.indexes:
                index.create(bind=schema_connection, checkfirst=True)
        _migrate_llm_model_pricing(connection)
        _seed_default_llm_model_pricing(connection)
        if schema_name == 'evaluation':
            evaluation_metadata.create_all(bind=schema_connection, checkfirst=True)
            create_evaluation_views(connection, schema_name=schema_name)
        elif schema_name == 'public':
            create_operational_views(connection, schema_name=schema_name)


def _trim_rag_result_message_columns(connection) -> None:
    """Keep generic user and assistant content out of RAG execution records."""
    connection.execute(text('ALTER TABLE rag_results DROP COLUMN IF EXISTS question'))
    connection.execute(text('ALTER TABLE rag_results DROP COLUMN IF EXISTS answer'))


def _migrate_chat_messages(connection) -> None:
    """Rename the chat request reference to its provider-neutral name."""
    connection.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'chat_messages'
                      AND column_name = 'rag_request_id'
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'chat_messages'
                      AND column_name = 'request_id'
                ) THEN
                    ALTER TABLE chat_messages
                    RENAME COLUMN rag_request_id TO request_id;
                END IF;
            END
            $$
            """
        )
    )


def _migrate_llm_model_pricing(connection) -> None:
    """Add pricing columns introduced after the initial table release."""
    connection.execute(
        text(
            """
            ALTER TABLE llm_model_pricing
            ADD COLUMN IF NOT EXISTS cached_input_cost_per_token NUMERIC(20, 12)
            """
        )
    )
    connection.execute(
        text(
            """
            UPDATE llm_model_pricing
            SET cached_input_cost_per_token = CASE
                WHEN provider = 'openai' AND model = 'gpt-4.1-mini'
                    THEN 0.0000001
                ELSE 0
            END
            WHERE cached_input_cost_per_token IS NULL
            """
        )
    )
    connection.execute(
        text(
            """
            ALTER TABLE llm_model_pricing
            ALTER COLUMN cached_input_cost_per_token SET NOT NULL
            """
        )
    )
    connection.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'ck_llm_model_pricing_cached_input_cost_non_negative'
                ) THEN
                    ALTER TABLE llm_model_pricing
                    ADD CONSTRAINT ck_llm_model_pricing_cached_input_cost_non_negative
                    CHECK (cached_input_cost_per_token >= 0);
                END IF;
            END
            $$
            """
        )
    )


def _migrate_llm_usage_events(connection) -> None:
    """Add evaluation run references to existing usage-event tables."""
    connection.execute(
        text('ALTER TABLE llm_usage_events ADD COLUMN IF NOT EXISTS rag_run_id UUID')
    )
    connection.execute(
        text('ALTER TABLE llm_usage_events ADD COLUMN IF NOT EXISTS judge_run_id UUID')
    )


def _seed_default_llm_model_pricing(connection) -> None:
    """Insert known pricing defaults without overwriting existing prices."""
    rows = [
        {
            'provider': provider,
            'model': model,
            **pricing,
        }
        for (provider, model), pricing in DEFAULT_LLM_MODEL_PRICING.items()
    ]
    for row in rows:
        existing = connection.execute(
            select(llm_model_pricing.c.pricing_id)
            .where(
                llm_model_pricing.c.provider == row['provider'],
                llm_model_pricing.c.model == row['model'],
            )
            .limit(1)
        ).first()
        if existing is None:
            connection.execute(insert(llm_model_pricing).values(row))


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


__all__ = [
    'DEFAULT_LLM_MODEL_PRICING',
    'SUPPORTED_SCHEMA_NAMES',
    'initialize_database',
]
