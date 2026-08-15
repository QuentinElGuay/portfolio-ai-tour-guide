"""Restore and clear reproducible corpora without duplicating database DDL."""

from pathlib import Path

from sqlalchemy.engine import Engine

from ai_tour_guide.knowledge_base.database.connection import create_database_engine
from ai_tour_guide.knowledge_base.database.init import (
    SUPPORTED_SCHEMA_NAMES,
    initialize_database,
)
from ai_tour_guide.knowledge_base.database.settings import DatabaseSettings

from .format import COPY_OPTIONS, CORPUS_FILES, DEFAULT_CORPUS_ROOT

_INSERT_EMBEDDING_MODELS = """
    INSERT INTO embedding_models (
        embedding_model_id, provider, model_name, model_revision, dimensions,
        normalized, tokenizer_name, tokenizer_revision, max_input_tokens,
        distance_metric, created_at
    )
    SELECT
        (data::jsonb ->> 'embedding_model_id')::bigint,
        data::jsonb ->> 'provider',
        data::jsonb ->> 'model_name',
        data::jsonb ->> 'model_revision',
        (data::jsonb ->> 'dimensions')::integer,
        (data::jsonb ->> 'normalized')::boolean,
        data::jsonb ->> 'tokenizer_name',
        data::jsonb ->> 'tokenizer_revision',
        (data::jsonb ->> 'max_input_tokens')::integer,
        data::jsonb ->> 'distance_metric',
        (data::jsonb ->> 'created_at')::timestamptz
    FROM corpus_import
"""

_INSERT_DOCUMENTS = """
    INSERT INTO documents (
        document_id, embedding_model_id, collection, version, title, source_url,
        publisher, publication_date, authors, subject, keywords, language,
        creator, producer, format, creation_date, modification_date,
        source_page_count, page_count, source_checksum, parser_version,
        chunking_version, target_chunk_chars, max_chunk_chars,
        section_chunk_min_depth, section_chunk_max_depth,
        target_chunk_tokens, max_chunk_tokens, chunk_overlap_tokens,
        embedded_at, created_at
    )
    SELECT
        (data::jsonb ->> 'document_id')::bigint,
        (data::jsonb ->> 'embedding_model_id')::bigint,
        data::jsonb ->> 'collection',
        data::jsonb ->> 'version',
        data::jsonb ->> 'title',
        data::jsonb ->> 'source_url',
        data::jsonb ->> 'publisher',
        (data::jsonb ->> 'publication_date')::date,
        ARRAY(SELECT jsonb_array_elements_text(data::jsonb -> 'authors')),
        data::jsonb ->> 'subject',
        ARRAY(SELECT jsonb_array_elements_text(data::jsonb -> 'keywords')),
        data::jsonb ->> 'language',
        data::jsonb ->> 'creator',
        data::jsonb ->> 'producer',
        data::jsonb ->> 'format',
        (data::jsonb ->> 'creation_date')::timestamptz,
        (data::jsonb ->> 'modification_date')::timestamptz,
        (data::jsonb ->> 'source_page_count')::integer,
        (data::jsonb ->> 'page_count')::integer,
        data::jsonb ->> 'source_checksum',
        data::jsonb ->> 'parser_version',
        data::jsonb ->> 'chunking_version',
        (data::jsonb ->> 'target_chunk_chars')::integer,
        (data::jsonb ->> 'max_chunk_chars')::integer,
        (data::jsonb ->> 'section_chunk_min_depth')::integer,
        (data::jsonb ->> 'section_chunk_max_depth')::integer,
        (data::jsonb ->> 'target_chunk_tokens')::integer,
        (data::jsonb ->> 'max_chunk_tokens')::integer,
        (data::jsonb ->> 'chunk_overlap_tokens')::integer,
        (data::jsonb ->> 'embedded_at')::timestamptz,
        (data::jsonb ->> 'created_at')::timestamptz
    FROM corpus_import
"""

_INSERT_DOCUMENT_CHUNKS = """
    INSERT INTO document_chunks (
        document_id, chunk_id, chunk_index, section_id, section_chunk_index,
        section_path, text, embedding_text, page_start, page_end,
        character_count, token_count, content_hash, embedding_input_sha256,
        embedding, created_at
    )
    SELECT
        (data::jsonb ->> 'document_id')::bigint,
        data::jsonb ->> 'chunk_id',
        (data::jsonb ->> 'chunk_index')::integer,
        data::jsonb ->> 'section_id',
        (data::jsonb ->> 'section_chunk_index')::integer,
        ARRAY(SELECT jsonb_array_elements_text(data::jsonb -> 'section_path')),
        data::jsonb ->> 'text',
        data::jsonb ->> 'embedding_text',
        (data::jsonb ->> 'page_start')::integer,
        (data::jsonb ->> 'page_end')::integer,
        (data::jsonb ->> 'character_count')::integer,
        (data::jsonb ->> 'token_count')::integer,
        data::jsonb ->> 'content_hash',
        data::jsonb ->> 'embedding_input_sha256',
        (data::jsonb ->> 'embedding')::vector,
        (data::jsonb ->> 'created_at')::timestamptz
    FROM corpus_import
"""


def clear_knowledge_base(
    *,
    engine: Engine | None = None,
    schema_name: str = 'public',
) -> None:
    """Truncate knowledge-base data while preserving the schema and tables."""
    _validate_schema(schema_name)
    owned_engine = engine is None
    if engine is None:
        engine = create_database_engine(DatabaseSettings(schema_name=schema_name))
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                'TRUNCATE TABLE document_chunks, documents, embedding_models RESTART IDENTITY'
            )
    finally:
        if owned_engine:
            engine.dispose()


def load_corpus(
    *,
    root: Path = DEFAULT_CORPUS_ROOT,
    engine: Engine | None = None,
    clear_first: bool = True,
    initialize_schema: bool = True,
    schema_name: str = 'public',
) -> Path:
    """Load a logical corpus, delegating table/schema creation to ``initialize_database``."""
    _validate_schema(schema_name)
    _require_corpus_files(root)
    owned_engine = engine is None
    if engine is None:
        engine = create_database_engine(DatabaseSettings(schema_name=schema_name))

    if initialize_schema:
        initialize_database(schema_name, engine=engine)

    try:
        raw_connection = engine.raw_connection()
        try:
            with raw_connection.cursor() as cursor:
                if clear_first:
                    cursor.execute(
                        'TRUNCATE TABLE document_chunks, documents, embedding_models RESTART IDENTITY'
                    )
                cursor.execute('CREATE TEMP TABLE corpus_import (data text NOT NULL) ON COMMIT DROP')
                _load_corpus_file(cursor, root / 'embedding_models.jsonl', _INSERT_EMBEDDING_MODELS)
                _load_corpus_file(cursor, root / 'documents.jsonl', _INSERT_DOCUMENTS)
                _load_corpus_file(cursor, root / 'document_chunks.jsonl', _INSERT_DOCUMENT_CHUNKS)
                _reset_identity_sequence(cursor, 'embedding_models', 'embedding_model_id')
                _reset_identity_sequence(cursor, 'documents', 'document_id')
            raw_connection.commit()
        except Exception:
            raw_connection.rollback()
            raise
        finally:
            raw_connection.close()
    finally:
        if owned_engine:
            engine.dispose()
    return root


def _validate_schema(schema_name: str) -> None:
    if schema_name not in SUPPORTED_SCHEMA_NAMES:
        choices = ', '.join(SUPPORTED_SCHEMA_NAMES)
        raise ValueError(f'Unsupported schema {schema_name!r}; choose one of: {choices}')


def _require_corpus_files(corpus_dir: Path) -> None:
    missing = [name for name in CORPUS_FILES if not (corpus_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing corpus file(s) in {corpus_dir}: {', '.join(missing)}"
        )


def _copy_jsonl_into_staging(cursor: object, path: Path) -> None:
    cursor.execute('TRUNCATE TABLE corpus_import')
    copy_sql = f'COPY corpus_import(data) FROM STDIN WITH ({COPY_OPTIONS})'
    with path.open('rb') as input_file, cursor.copy(copy_sql) as copy:
        while data := input_file.read(1024 * 1024):
            copy.write(data)


def _load_corpus_file(cursor: object, path: Path, insert_sql: str) -> None:
    _copy_jsonl_into_staging(cursor, path)
    cursor.execute(insert_sql)


def _reset_identity_sequence(cursor: object, table: str, id_column: str) -> None:
    cursor.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', '{id_column}'),
            COALESCE(MAX({id_column}), 1),
            MAX({id_column}) IS NOT NULL
        )
        FROM {table}
        """
    )


__all__ = ['clear_knowledge_base', 'load_corpus']
