"""Skeleton tests for database initialization."""


def test_initialize_database_creates_extension_schema_tables_and_indexes() -> None:
    """Call ``initialize_database(schema_name, engine=engine)`` with a mocked SQLAlchemy Engine.

    Required mocks: engine.begin context, connection.execute, ``metadata.create_all`` and index ``create``.
    Expected verification: pgvector extension and schema creation execute before Core metadata creates
    tables/indexes, without any duplicated hand-written DDL.
    """
    pass


def test_initialize_database_rejects_unsupported_schema() -> None:
    """Call ``initialize_database`` with a schema not present in ``SUPPORTED_SCHEMA_NAMES``.

    Required inputs: one invalid schema string; no engine should be needed.
    Expected verification: ValueError is raised before creating an engine or executing SQL.
    """
    pass


def test_initialize_database_disposes_only_owned_engine() -> None:
    """Call ``initialize_database`` once with no engine and once with an injected engine.

    Required mocks: ``create_database_engine`` plus mocked owned/injected engines.
    Expected verification: internally-created engine is disposed and caller-owned engine is not.
    """
    pass
