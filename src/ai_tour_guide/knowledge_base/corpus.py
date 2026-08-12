"""Export, restore, and clear reproducible knowledge-base corpora.

Corpora are logical JSONL dumps of the persisted knowledge-base state. They
preserve pgvector embeddings so retrieval benchmarks can run against a fixed
vector space. PostgreSQL-generated columns such as ``search_vector`` are not
exported; PostgreSQL recreates them when rows are restored.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.engine import Engine

from ai_tour_guide.knowledge_base.connection import create_database_engine
from ai_tour_guide.knowledge_base.init_db import initialize_database

_COPY_OPTIONS = "FORMAT CSV, DELIMITER E'\\x01', QUOTE E'\\x02'"

CORPUS_FILES = (
    "embedding_models.jsonl",
    "documents.jsonl",
    "document_chunks.jsonl",
)

_EXPORTS = {
    "embedding_models.jsonl": """
        SELECT jsonb_build_object(
            'embedding_model_id', embedding_model_id,
            'provider', provider,
            'model_name', model_name,
            'model_revision', model_revision,
            'dimensions', dimensions,
            'normalized', normalized,
            'tokenizer_name', tokenizer_name,
            'tokenizer_revision', tokenizer_revision,
            'max_input_tokens', max_input_tokens,
            'distance_metric', distance_metric,
            'created_at', created_at
        )::text
        FROM embedding_models
        ORDER BY embedding_model_id
    """,
    "documents.jsonl": """
        SELECT jsonb_build_object(
            'document_id', document_id,
            'embedding_model_id', embedding_model_id,
            'collection', collection,
            'version', version,
            'title', title,
            'source_url', source_url,
            'publisher', publisher,
            'publication_date', publication_date,
            'authors', authors,
            'subject', subject,
            'keywords', keywords,
            'language', language,
            'creator', creator,
            'producer', producer,
            'format', format,
            'creation_date', creation_date,
            'modification_date', modification_date,
            'source_page_count', source_page_count,
            'page_count', page_count,
            'source_checksum', source_checksum,
            'parser_version', parser_version,
            'chunking_version', chunking_version,
            'target_chunk_chars', target_chunk_chars,
            'max_chunk_chars', max_chunk_chars,
            'target_chunk_tokens', target_chunk_tokens,
            'max_chunk_tokens', max_chunk_tokens,
            'chunk_overlap_tokens', chunk_overlap_tokens,
            'embedded_at', embedded_at,
            'created_at', created_at
        )::text
        FROM documents
        ORDER BY document_id
    """,
    "document_chunks.jsonl": """
        SELECT jsonb_build_object(
            'document_id', document_id,
            'chunk_id', chunk_id,
            'chunk_index', chunk_index,
            'section_path', section_path,
            'text', text,
            'embedding_text', embedding_text,
            'page_start', page_start,
            'page_end', page_end,
            'character_count', character_count,
            'token_count', token_count,
            'content_hash', content_hash,
            'embedding_input_sha256', embedding_input_sha256,
            'embedding', embedding::text,
            'created_at', created_at
        )::text
        FROM document_chunks
        ORDER BY document_id, chunk_index, chunk_id
    """,
}

_INSERT_EMBEDDING_MODELS = """
    INSERT INTO embedding_models (
        embedding_model_id,
        provider,
        model_name,
        model_revision,
        dimensions,
        normalized,
        tokenizer_name,
        tokenizer_revision,
        max_input_tokens,
        distance_metric,
        created_at
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
        document_id,
        embedding_model_id,
        collection,
        version,
        title,
        source_url,
        publisher,
        publication_date,
        authors,
        subject,
        keywords,
        language,
        creator,
        producer,
        format,
        creation_date,
        modification_date,
        source_page_count,
        page_count,
        source_checksum,
        parser_version,
        chunking_version,
        target_chunk_chars,
        max_chunk_chars,
        target_chunk_tokens,
        max_chunk_tokens,
        chunk_overlap_tokens,
        embedded_at,
        created_at
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
        (data::jsonb ->> 'target_chunk_tokens')::integer,
        (data::jsonb ->> 'max_chunk_tokens')::integer,
        (data::jsonb ->> 'chunk_overlap_tokens')::integer,
        (data::jsonb ->> 'embedded_at')::timestamptz,
        (data::jsonb ->> 'created_at')::timestamptz
    FROM corpus_import
"""

_INSERT_DOCUMENT_CHUNKS = """
    INSERT INTO document_chunks (
        document_id,
        chunk_id,
        chunk_index,
        section_path,
        text,
        embedding_text,
        page_start,
        page_end,
        character_count,
        token_count,
        content_hash,
        embedding_input_sha256,
        embedding,
        created_at
    )
    SELECT
        (data::jsonb ->> 'document_id')::bigint,
        data::jsonb ->> 'chunk_id',
        (data::jsonb ->> 'chunk_index')::integer,
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



DEFAULT_CORPUS_ROOT = Path("fixtures/corpus")


def corpus_directory(version: int, *, root: Path = DEFAULT_CORPUS_ROOT) -> Path:
    """Return the directory for one versioned corpus fixture."""
    if version <= 0:
        raise ValueError("version must be a positive integer")
    return root / f"v{version}"


def export_corpus(
    version: int,
    *,
    root: Path = DEFAULT_CORPUS_ROOT,
    engine: Engine | None = None,
) -> Path:
    """Export the current knowledge-base state to ``root/v{version}``.

    Existing files with the same names are replaced. The caller is responsible
    for deciding whether overwriting an existing corpus version is appropriate.
    """
    output_dir = corpus_directory(version, root=root)
    output_dir.mkdir(parents=True, exist_ok=True)
    owned_engine = engine is None
    engine = engine or create_database_engine()

    try:
        raw_connection = engine.raw_connection()
        try:
            with raw_connection.cursor() as cursor:
                for filename, select_sql in _EXPORTS.items():
                    output_path = output_dir / filename
                    copy_sql = f"COPY ({select_sql}) TO STDOUT WITH ({_COPY_OPTIONS})"
                    with output_path.open("wb") as output_file:
                        with cursor.copy(copy_sql) as copy:
                            for data in copy:
                                output_file.write(data)
        finally:
            raw_connection.close()
    finally:
        if owned_engine:
            engine.dispose()

    return output_dir


def clear_knowledge_base(*, engine: Engine | None = None) -> None:
    """Delete all persisted knowledge-base rows and reset identity sequences."""
    owned_engine = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE document_chunks, documents, embedding_models "
                "RESTART IDENTITY"
            )
    finally:
        if owned_engine:
            engine.dispose()


def load_corpus(
    version: int,
    *,
    root: Path = DEFAULT_CORPUS_ROOT,
    engine: Engine | None = None,
    clear_first: bool = True,
    initialize_schema: bool = True,
) -> Path:
    """Load ``root/v{version}`` into the configured knowledge base."""
    corpus_dir = corpus_directory(version, root=root)
    _require_corpus_files(corpus_dir)

    if initialize_schema:
        # TODO: Refactor initialize_database() to accept an Engine so callers can
        # reuse one connection pool throughout corpus loading.
        initialize_database()

    owned_engine = engine is None
    engine = engine or create_database_engine()
    try:
        raw_connection = engine.raw_connection()
        try:
            with raw_connection.cursor() as cursor:
                if clear_first:
                    cursor.execute(
                        "TRUNCATE TABLE document_chunks, documents, embedding_models "
                        "RESTART IDENTITY"
                    )

                cursor.execute(
                    "CREATE TEMP TABLE corpus_import (data text NOT NULL) ON COMMIT DROP"
                )

                _load_corpus_file(
                    cursor,
                    corpus_dir / "embedding_models.jsonl",
                    _INSERT_EMBEDDING_MODELS,
                )
                _load_corpus_file(
                    cursor,
                    corpus_dir / "documents.jsonl",
                    _INSERT_DOCUMENTS,
                )
                _load_corpus_file(
                    cursor,
                    corpus_dir / "document_chunks.jsonl",
                    _INSERT_DOCUMENT_CHUNKS,
                )

                _reset_identity_sequence(cursor, "embedding_models", "embedding_model_id")
                _reset_identity_sequence(cursor, "documents", "document_id")

            raw_connection.commit()
        except Exception:
            raw_connection.rollback()
            raise
        finally:
            raw_connection.close()
    finally:
        if owned_engine:
            engine.dispose()

    return corpus_dir


@contextmanager
def corpus_context(
    version: int,
    *,
    root: Path = DEFAULT_CORPUS_ROOT,
    clear_after: bool = True,
) -> Iterator[None]:
    """Load one corpus for a scoped operation and optionally clear it afterward.

    This does not restore any database state that existed before entering the
    context. It loads the selected corpus and, by default, leaves the knowledge
    base empty on exit.
    """
    load_corpus(version, root=root)
    try:
        yield
    finally:
        if clear_after:
            clear_knowledge_base()


def _require_corpus_files(corpus_dir: Path) -> None:
    missing = [name for name in CORPUS_FILES if not (corpus_dir / name).is_file()]
    if missing:
        joined = ", ".join(missing)
        raise FileNotFoundError(f"Missing corpus file(s) in {corpus_dir}: {joined}")


def _copy_jsonl_into_staging(cursor: object, path: Path) -> None:
    cursor.execute("TRUNCATE TABLE corpus_import")
    copy_sql = f"COPY corpus_import(data) FROM STDIN WITH ({_COPY_OPTIONS})"

    with path.open("rb") as input_file:
        with cursor.copy(copy_sql) as copy:
            while data := input_file.read(1024 * 1024):
                copy.write(data)


def _load_corpus_file(cursor: object, path: Path, insert_sql: str) -> None:
    _copy_jsonl_into_staging(cursor, path)
    cursor.execute(insert_sql)


def _reset_identity_sequence(cursor: object, table: str, id_column: str) -> None:
    # ``table`` and ``id_column`` are internal constants, never user input.
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


__all__ = [
    "CORPUS_FILES",
    "DEFAULT_CORPUS_ROOT",
    "clear_knowledge_base",
    "corpus_context",
    "corpus_directory",
    "export_corpus",
    "load_corpus",
]
