import os

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR


try:
    EMBEDDING_DIMENSIONS = int(os.environ['EMBEDDING_DIMENSIONS'])
except KeyError as exc:
    raise RuntimeError(
        'EMBEDDING_DIMENSIONS must be configured before loading the database schema'
    ) from exc


metadata = MetaData()


embedding_models = Table(
    'embedding_models',
    metadata,
    Column(
        'embedding_model_id',
        BigInteger,
        Identity(),
        primary_key=True,
    ),
    Column(
        'provider',
        Text,
        nullable=False,
    ),
    Column(
        'model_name',
        Text,
        nullable=False,
    ),
    Column(
        'model_revision',
        Text,
        nullable=False,
        server_default=text("'default'"),
    ),
    Column(
        'dimensions',
        Integer,
        nullable=False,
    ),
    Column(
        'tokenizer_name',
        Text,
    ),
    Column(
        'tokenizer_revision',
        Text,
    ),
    Column(
        'max_input_tokens',
        Integer,
    ),
    Column(
        'distance_metric',
        Text,
        nullable=False,
        server_default=text("'cosine'"),
    ),
    Column(
        'created_at',
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    UniqueConstraint(
        'provider',
        'model_name',
        'model_revision',
        name='uq_embedding_models_identity',
    ),
    CheckConstraint(
        'dimensions > 0',
        name='ck_embedding_models_dimensions_positive',
    ),
    CheckConstraint(
        f'dimensions = {EMBEDDING_DIMENSIONS}',
        name='ck_embedding_models_dimensions_match_vector',
    ),
    CheckConstraint(
        'max_input_tokens IS NULL OR max_input_tokens > 0',
        name='ck_embedding_models_max_input_tokens_positive',
    ),
    CheckConstraint(
        "distance_metric IN ('cosine', 'l2', 'inner_product')",
        name='ck_embedding_models_distance_metric',
    ),
)


documents = Table(
    'documents',
    metadata,
    Column(
        'document_id',
        BigInteger,
        Identity(),
        primary_key=True,
    ),
    Column(
        'embedding_model_id',
        BigInteger,
        ForeignKey('embedding_models.embedding_model_id'),
    ),
    Column(
        'collection',
        Text,
        nullable=False,
    ),
    Column(
        'version',
        Text,
    ),
    Column(
        'title',
        Text,
        nullable=False,
    ),
    Column(
        'pdf_url',
        Text,
        nullable=False,
    ),
    Column(
        'publisher',
        Text,
    ),
    Column(
        'publication_date',
        Date,
    ),
    Column(
        'authors',
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    ),
    Column(
        'subject',
        Text,
    ),
    Column(
        'keywords',
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    ),
    Column(
        'language',
        Text,
    ),
    Column(
        'creator',
        Text,
    ),
    Column(
        'producer',
        Text,
    ),
    Column(
        'pdf_format',
        Text,
    ),
    # Retained as text because the source values currently use the
    # PDF date format: D:20251125102910+00'00'
    Column(
        'pdf_creation_date',
        Text,
    ),
    Column(
        'pdf_modification_date',
        Text,
    ),
    Column(
        'source_page_count',
        Integer,
    ),
    Column(
        'parsed_page_count',
        Integer,
    ),
    # Processing provenance. These columns may remain null until their
    # corresponding functionality is implemented by the ingestion pipeline.
    Column(
        'source_hash',
        Text,
    ),
    Column(
        'parser_version',
        Text,
    ),
    Column(
        'chunking_version',
        Text,
    ),
    Column(
        'target_chunk_chars',
        Integer,
    ),
    Column(
        'max_chunk_chars',
        Integer,
    ),
    Column(
        'target_chunk_tokens',
        Integer,
    ),
    Column(
        'max_chunk_tokens',
        Integer,
    ),
    Column(
        'chunk_overlap_tokens',
        Integer,
    ),
    # Set when every chunk belonging to this document has been embedded
    # successfully with embedding_model_id.
    Column(
        'embedded_at',
        DateTime(timezone=True),
    ),
    Column(
        'created_at',
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    UniqueConstraint(
        'collection',
        'pdf_url',
        name='uq_documents_collection_pdf_url',
    ),
    CheckConstraint(
        "btrim(collection) <> ''",
        name='ck_documents_collection_not_empty',
    ),
    CheckConstraint(
        "version IS NULL OR btrim(version) <> ''",
        name='ck_documents_version_not_empty',
    ),
    CheckConstraint(
        'source_page_count IS NULL OR source_page_count > 0',
        name='ck_documents_source_page_count_positive',
    ),
    CheckConstraint(
        'parsed_page_count IS NULL OR parsed_page_count >= 0',
        name='ck_documents_parsed_page_count_positive',
    ),
    CheckConstraint(
        'target_chunk_chars IS NULL OR target_chunk_chars > 0',
        name='ck_documents_target_chunk_chars_positive',
    ),
    CheckConstraint(
        'max_chunk_chars IS NULL OR max_chunk_chars > 0',
        name='ck_documents_max_chunk_chars_positive',
    ),
    CheckConstraint(
        """
        target_chunk_chars IS NULL
        OR max_chunk_chars IS NULL
        OR target_chunk_chars <= max_chunk_chars
        """,
        name='ck_documents_chunk_chars_range',
    ),
    CheckConstraint(
        'target_chunk_tokens IS NULL OR target_chunk_tokens > 0',
        name='ck_documents_target_chunk_tokens_positive',
    ),
    CheckConstraint(
        'max_chunk_tokens IS NULL OR max_chunk_tokens > 0',
        name='ck_documents_max_chunk_tokens_positive',
    ),
    CheckConstraint(
        """
        target_chunk_tokens IS NULL
        OR max_chunk_tokens IS NULL
        OR target_chunk_tokens <= max_chunk_tokens
        """,
        name='ck_documents_chunk_tokens_range',
    ),
    CheckConstraint(
        'chunk_overlap_tokens IS NULL OR chunk_overlap_tokens >= 0',
        name='ck_documents_chunk_overlap_tokens_positive',
    ),
    CheckConstraint(
        """
        chunk_overlap_tokens IS NULL
        OR max_chunk_tokens IS NULL
        OR chunk_overlap_tokens < max_chunk_tokens
        """,
        name='ck_documents_chunk_overlap_tokens_range',
    ),
    CheckConstraint(
        'embedded_at IS NULL OR embedding_model_id IS NOT NULL',
        name='ck_documents_embedded_model_required',
    ),
)


document_chunks = Table(
    'document_chunks',
    metadata,
    Column(
        'chunk_id',
        BigInteger,
        Identity(),
        primary_key=True,
    ),
    Column(
        'document_id',
        BigInteger,
        ForeignKey(
            'documents.document_id',
            ondelete='CASCADE',
        ),
        nullable=False,
    ),
    # The identifier generated by chunking.py, such as:
    # guide-discover-brittany:chunk-0001
    Column(
        'chunk_key',
        Text,
        nullable=False,
    ),
    Column(
        'chunk_index',
        Integer,
        nullable=False,
    ),
    Column(
        'section_path',
        ARRAY(Text),
        nullable=False,
    ),
    Column(
        'text',
        Text,
        nullable=False,
    ),
    # Exact value sent to the embedding model:
    # document title + breadcrumb + chunk text
    Column(
        'embedding_text',
        Text,
        nullable=False,
    ),
    Column(
        'page_start',
        Integer,
    ),
    Column(
        'page_end',
        Integer,
    ),
    Column(
        'character_count',
        Integer,
        nullable=False,
    ),
    Column(
        'token_count',
        Integer,
    ),
    Column(
        'content_hash',
        Text,
    ),
    Column(
        'embedding_input_hash',
        Text,
    ),
    # Nullable until the chunk has been embedded. The model and tokenizer
    # metadata are inherited through documents.embedding_model_id.
    Column(
        'embedding',
        VECTOR(EMBEDDING_DIMENSIONS),
    ),
    # PostgreSQL maintains this column automatically.
    Column(
        'search_vector',
        TSVECTOR,
        Computed(
            """
            to_tsvector(
                'english',
                coalesce(embedding_text, '')
            )
            """,
            persisted=True,
        ),
    ),
    Column(
        'created_at',
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    UniqueConstraint(
        'document_id',
        'chunk_key',
        name='uq_document_chunks_key',
    ),
    UniqueConstraint(
        'document_id',
        'chunk_index',
        name='uq_document_chunks_index',
    ),
    CheckConstraint(
        'chunk_index >= 0',
        name='ck_document_chunks_index_positive',
    ),
    CheckConstraint(
        'character_count > 0',
        name='ck_document_chunks_character_count_positive',
    ),
    CheckConstraint(
        'token_count IS NULL OR token_count > 0',
        name='ck_document_chunks_token_count_positive',
    ),
    CheckConstraint(
        'page_start IS NULL OR page_start > 0',
        name='ck_document_chunks_page_start_positive',
    ),
    CheckConstraint(
        'page_end IS NULL OR page_end > 0',
        name='ck_document_chunks_page_end_positive',
    ),
    CheckConstraint(
        """
        page_start IS NULL
        OR page_end IS NULL
        OR page_end >= page_start
        """,
        name='ck_document_chunks_page_range',
    ),
    CheckConstraint(
        'embedding IS NULL OR embedding_input_hash IS NOT NULL',
        name='ck_document_chunks_embedding_input_hash_required',
    ),
)


Index(
    'ix_documents_embedding_model_id',
    documents.c.embedding_model_id,
)

Index(
    'ix_documents_source_hash',
    documents.c.source_hash,
)

Index(
    'ix_document_chunks_document_id',
    document_chunks.c.document_id,
)

Index(
    'ix_document_chunks_search_vector',
    document_chunks.c.search_vector,
    postgresql_using='gin',
)
