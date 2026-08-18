"""Export a reproducible logical corpus including persisted embeddings."""

from pathlib import Path
from typing import Any, LiteralString, cast

from psycopg import Cursor, sql
from sqlalchemy.engine import Engine

from ai_tour_guide.knowledge_base.database.connection import database_engine

from .format import DEFAULT_CORPUS_ROOT

_EXPORTS: dict[str, LiteralString] = {
    'embedding_models.jsonl': """
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
    'documents.jsonl': """
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
            'section_chunk_min_depth', section_chunk_min_depth,
            'section_chunk_max_depth', section_chunk_max_depth,
            'target_chunk_tokens', target_chunk_tokens,
            'max_chunk_tokens', max_chunk_tokens,
            'chunk_overlap_tokens', chunk_overlap_tokens,
            'embedded_at', embedded_at,
            'created_at', created_at
        )::text
        FROM documents
        ORDER BY document_id
    """,
    'document_chunks.jsonl': """
        SELECT jsonb_build_object(
            'document_id', document_id,
            'chunk_id', chunk_id,
            'chunk_index', chunk_index,
            'section_id', section_id,
            'section_chunk_index', section_chunk_index,
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


def export_corpus(
    *,
    root: Path = DEFAULT_CORPUS_ROOT,
    engine: Engine | None = None,
) -> Path:
    """Export the configured knowledge-base state into the logical JSONL corpus format."""
    root.mkdir(parents=True, exist_ok=True)
    with database_engine(engine) as db_engine:
        raw_connection = db_engine.raw_connection()
        try:
            cursor = cast(Cursor[Any], raw_connection.cursor())
            try:
                for filename, select_sql in _EXPORTS.items():
                    output_path = root / filename
                    copy_sql = sql.SQL(
                        'COPY ({select_sql}) TO STDOUT WITH ({copy_options})'
                    ).format(
                        select_sql=sql.SQL(select_sql),
                        copy_options=sql.SQL(
                            "FORMAT CSV, DELIMITER E'\\x01', QUOTE E'\\x02'"
                        ),
                    )
                    with (
                        output_path.open('wb') as output_file,
                        cursor.copy(copy_sql) as copy,
                    ):
                        for data in copy:
                            output_file.write(data)
            finally:
                cursor.close()
        finally:
            raw_connection.close()
    return root


__all__ = ['export_corpus']
