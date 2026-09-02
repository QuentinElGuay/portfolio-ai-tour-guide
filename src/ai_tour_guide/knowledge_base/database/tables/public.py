"""SQLAlchemy Core schema definitions for the knowledge-base tables."""

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
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
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

from ai_tour_guide.embedding.settings import EmbeddingSettings

EMBEDDING_DIMENSIONS = EmbeddingSettings().dimensions
metadata = MetaData()

llm_model_pricing = Table(
    'llm_model_pricing',
    metadata,
    Column('pricing_id', BigInteger, Identity(), primary_key=True),
    Column('provider', Text, nullable=False),
    Column('model', Text, nullable=False),
    Column('input_cost_per_token', Numeric(20, 12), nullable=False),
    Column('cached_input_cost_per_token', Numeric(20, 12), nullable=False),
    Column('output_cost_per_token', Numeric(20, 12), nullable=False),
    Column('currency', Text, nullable=False, server_default=text("'USD'")),
    Column(
        'effective_from',
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    UniqueConstraint(
        'provider',
        'model',
        'effective_from',
        name='uq_llm_model_pricing_version',
    ),
    CheckConstraint(
        'input_cost_per_token >= 0',
        name='ck_llm_model_pricing_input_cost_non_negative',
    ),
    CheckConstraint(
        'cached_input_cost_per_token >= 0',
        name='ck_llm_model_pricing_cached_input_cost_non_negative',
    ),
    CheckConstraint(
        'output_cost_per_token >= 0',
        name='ck_llm_model_pricing_output_cost_non_negative',
    ),
    CheckConstraint(
        "btrim(provider) <> '' AND btrim(model) <> ''",
        name='ck_llm_model_pricing_identity_not_empty',
    ),
)

llm_usage_events = Table(
    'llm_usage_events',
    metadata,
    Column('usage_event_id', BigInteger, Identity(), primary_key=True),
    Column('request_id', UUID(as_uuid=True)),
    Column('rag_run_id', UUID(as_uuid=True)),
    Column('judge_run_id', UUID(as_uuid=True)),
    Column('call_type', Text, nullable=False),
    Column('provider', Text, nullable=False),
    Column('model', Text, nullable=False),
    Column('input_tokens', BigInteger),
    Column('cached_input_tokens', BigInteger),
    Column('output_tokens', BigInteger),
    Column('total_tokens', BigInteger),
    Column('pricing_id', BigInteger, ForeignKey('llm_model_pricing.pricing_id')),
    Column('input_cost', Numeric(20, 12)),
    Column('output_cost', Numeric(20, 12)),
    Column('total_cost', Numeric(20, 12)),
    Column('currency', Text),
    Column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column(
        'created_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint(
        "call_type IN ('answer', 'judge', 'embedding', 'other')",
        name='ck_llm_usage_events_call_type',
    ),
    CheckConstraint(
        'input_tokens IS NULL OR input_tokens >= 0',
        name='ck_llm_usage_events_input_tokens_non_negative',
    ),
    CheckConstraint(
        'cached_input_tokens IS NULL OR cached_input_tokens >= 0',
        name='ck_llm_usage_events_cached_input_tokens_non_negative',
    ),
    CheckConstraint(
        'output_tokens IS NULL OR output_tokens >= 0',
        name='ck_llm_usage_events_output_tokens_non_negative',
    ),
    CheckConstraint(
        'total_tokens IS NULL OR total_tokens >= 0',
        name='ck_llm_usage_events_total_tokens_non_negative',
    ),
    CheckConstraint(
        'input_cost IS NULL OR input_cost >= 0',
        name='ck_llm_usage_events_input_cost_non_negative',
    ),
    CheckConstraint(
        'output_cost IS NULL OR output_cost >= 0',
        name='ck_llm_usage_events_output_cost_non_negative',
    ),
    CheckConstraint(
        'total_cost IS NULL OR total_cost >= 0',
        name='ck_llm_usage_events_total_cost_non_negative',
    ),
)

embedding_models = Table(
    'embedding_models',
    metadata,
    Column('embedding_model_id', BigInteger, Identity(), primary_key=True),
    Column('provider', Text, nullable=False),
    Column('model_name', Text, nullable=False),
    Column('model_revision', Text, nullable=False, server_default=text("'default'")),
    Column('dimensions', Integer, nullable=False),
    Column('normalized', Boolean, nullable=False),
    Column('tokenizer_name', Text),
    Column('tokenizer_revision', Text),
    Column('max_input_tokens', Integer),
    Column('distance_metric', Text, nullable=False, server_default=text("'cosine'")),
    Column(
        'created_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint(
        'provider',
        'model_name',
        'model_revision',
        name='uq_embedding_models_identity',
    ),
    CheckConstraint('dimensions > 0', name='ck_embedding_models_dimensions_positive'),
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
    Column('document_id', BigInteger, Identity(), primary_key=True),
    Column(
        'embedding_model_id',
        BigInteger,
        ForeignKey('embedding_models.embedding_model_id'),
        nullable=False,
    ),
    Column('collection', Text),
    Column('version', Text),
    Column('title', Text, nullable=False),
    Column('destination', Text, nullable=False),
    Column('source_url', Text, nullable=False),
    Column('publisher', Text),
    Column('publication_date', Date),
    Column('authors', ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")),
    Column('subject', Text),
    Column(
        'keywords', ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    ),
    Column('language', Text),
    Column('creator', Text),
    Column('producer', Text),
    Column('format', Text),
    Column('creation_date', DateTime(timezone=True)),
    Column('modification_date', DateTime(timezone=True)),
    Column('source_page_count', Integer),
    Column('page_count', Integer),
    Column('source_checksum', Text),
    Column('parser_version', Text),
    Column('chunking_version', Text),
    Column('target_chunk_chars', Integer),
    Column('max_chunk_chars', Integer),
    Column('section_chunk_min_depth', Integer),
    Column('section_chunk_max_depth', Integer),
    Column('target_chunk_tokens', Integer),
    Column('max_chunk_tokens', Integer),
    Column('chunk_overlap_tokens', Integer),
    Column('embedded_at', DateTime(timezone=True)),
    Column(
        'created_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint(
        'source_url',
        'version',
        name='uq_documents_source_url_version',
        postgresql_nulls_not_distinct=True,
    ),
    CheckConstraint(
        "collection IS NULL OR btrim(collection) <> ''",
        name='ck_documents_collection_not_empty',
    ),
    CheckConstraint(
        "version IS NULL OR btrim(version) <> ''", name='ck_documents_version_not_empty'
    ),
    CheckConstraint(
        'source_page_count IS NULL OR source_page_count > 0',
        name='ck_documents_source_page_count_positive',
    ),
    CheckConstraint(
        'page_count IS NULL OR page_count >= 0',
        name='ck_documents_page_count_non_negative',
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
        'target_chunk_chars IS NULL OR max_chunk_chars IS NULL OR target_chunk_chars <= max_chunk_chars',
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
        'target_chunk_tokens IS NULL OR max_chunk_tokens IS NULL OR target_chunk_tokens <= max_chunk_tokens',
        name='ck_documents_chunk_tokens_range',
    ),
    CheckConstraint(
        'chunk_overlap_tokens IS NULL OR chunk_overlap_tokens >= 0',
        name='ck_documents_chunk_overlap_tokens_positive',
    ),
    CheckConstraint(
        'chunk_overlap_tokens IS NULL OR max_chunk_tokens IS NULL OR chunk_overlap_tokens < max_chunk_tokens',
        name='ck_documents_chunk_overlap_tokens_range',
    ),
)

document_chunks = Table(
    'document_chunks',
    metadata,
    Column(
        'document_id',
        BigInteger,
        ForeignKey('documents.document_id', ondelete='CASCADE'),
        nullable=False,
        primary_key=True,
    ),
    Column('chunk_id', Text, nullable=False, primary_key=True),
    Column('chunk_index', Integer, nullable=False),
    Column('section_id', Text, nullable=False),
    Column('section_chunk_index', Integer),
    Column('section_path', ARRAY(Text), nullable=False),
    Column('text', Text, nullable=False),
    Column('embedding_text', Text, nullable=False),
    Column('page_start', Integer),
    Column('page_end', Integer),
    Column('character_count', Integer, nullable=False),
    Column('token_count', Integer),
    Column('content_hash', Text),
    Column('embedding_input_sha256', Text),
    Column('embedding', VECTOR(EMBEDDING_DIMENSIONS)),
    Column(
        'search_vector',
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(embedding_text, ''))", persisted=True
        ),
    ),
    Column(
        'created_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint('document_id', 'chunk_index', name='uq_document_chunks_index'),
    CheckConstraint('chunk_index >= 0', name='ck_document_chunks_index_positive'),
    CheckConstraint(
        'section_chunk_index IS NULL OR section_chunk_index >= 0',
        name='ck_document_chunks_section_index_positive',
    ),
    CheckConstraint(
        'character_count > 0', name='ck_document_chunks_character_count_positive'
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
        'page_end IS NULL OR page_end > 0', name='ck_document_chunks_page_end_positive'
    ),
    CheckConstraint(
        'page_start IS NULL OR page_end IS NULL OR page_end >= page_start',
        name='ck_document_chunks_page_range',
    ),
    CheckConstraint(
        'embedding IS NULL OR embedding_input_sha256 IS NOT NULL',
        name='ck_document_chunks_embedding_input_sha256_required',
    ),
)

rag_results = Table(
    'rag_results',
    metadata,
    Column('success', Boolean, nullable=False),
    Column('error_stage', Text),
    Column('error_type', Text),
    Column('error_message', Text),
    Column('search_mode', Text, nullable=False),
    Column('retrieval_k', Integer, nullable=False),
    Column('search_result_count', Integer, nullable=False),
    Column('retrieved_context_count', Integer, nullable=False),
    Column('source_count', Integer, nullable=False),
    Column('citation_count', Integer, nullable=False),
    Column('invalid_citation_count', Integer, nullable=False),
    Column('retrieval_latency_ms', Integer),
    Column('llm_provider', Text),
    Column('llm_model', Text),
    Column('input_tokens', BigInteger),
    Column('output_tokens', BigInteger),
    Column('total_tokens', BigInteger),
    Column('generation_latency_ms', Integer),
    Column('total_latency_ms', Integer),
    Column('request_id', UUID(as_uuid=True), primary_key=True),
    Column('rag_result_schema_version', Integer, nullable=False),
    Column('rag_trace', JSONB, nullable=False),
    Column(
        'created_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint('retrieval_k > 0', name='ck_rag_results_retrieval_k_positive'),
    CheckConstraint(
        "search_mode IN ('vector', 'text', 'hybrid')",
        name='ck_rag_results_search_mode',
    ),
    CheckConstraint(
        'retrieved_context_count >= 0 AND search_result_count >= 0 '
        'AND source_count >= 0 AND citation_count >= 0 '
        'AND invalid_citation_count >= 0',
        name='ck_rag_results_counts_non_negative',
    ),
    CheckConstraint(
        'input_tokens IS NULL OR input_tokens >= 0',
        name='ck_rag_results_input_tokens_non_negative',
    ),
    CheckConstraint(
        'output_tokens IS NULL OR output_tokens >= 0',
        name='ck_rag_results_output_tokens_non_negative',
    ),
    CheckConstraint(
        'total_tokens IS NULL OR total_tokens >= 0',
        name='ck_rag_results_total_tokens_non_negative',
    ),
)

chat_messages = Table(
    'chat_messages',
    metadata,
    Column('message_id', UUID(as_uuid=True), primary_key=True),
    Column('session_id', UUID(as_uuid=True), nullable=False),
    Column('role', Text, nullable=False),
    Column('content', Text, nullable=False),
    Column('flow_step', Text),
    Column('input_id', Text),
    Column('rag_request_id', UUID(as_uuid=True)),
    Column('sources', JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column('trace', JSONB),
    Column('buttons', JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column(
        'created_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint(
        "role IN ('user', 'assistant', 'system')", name='ck_chat_messages_role'
    ),
)

chat_feedback = Table(
    'chat_feedback',
    metadata,
    Column('feedback_id', BigInteger, Identity(), primary_key=True),
    Column(
        'message_id',
        UUID(as_uuid=True),
        ForeignKey('chat_messages.message_id', ondelete='CASCADE'),
        nullable=False,
    ),
    Column('helpful', Boolean, nullable=False),
    Column('comment', Text),
    Column(
        'created_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint(
        "comment IS NULL OR btrim(comment) <> ''",
        name='ck_rag_feedback_comment_not_empty',
    ),
    CheckConstraint(
        'comment IS NULL OR helpful IS NOT NULL',
        name='ck_rag_feedback_comment_requires_rating',
    ),
)

Index('ix_documents_embedding_model_id', documents.c.embedding_model_id)
Index('ix_documents_source_checksum', documents.c.source_checksum)
Index(
    'ix_document_chunks_search_vector',
    document_chunks.c.search_vector,
    postgresql_using='gin',
)
Index(
    'ix_document_chunks_section_order',
    document_chunks.c.document_id,
    document_chunks.c.section_id,
    document_chunks.c.section_chunk_index,
)
Index(
    'ix_document_chunks_embedding_cosine_hnsw',
    document_chunks.c.embedding,
    postgresql_using='hnsw',
    postgresql_ops={'embedding': 'vector_cosine_ops'},
)
Index(
    'ix_document_chunks_embedding_l2_hnsw',
    document_chunks.c.embedding,
    postgresql_using='hnsw',
    postgresql_ops={'embedding': 'vector_l2_ops'},
)
Index(
    'ix_document_chunks_embedding_inner_product_hnsw',
    document_chunks.c.embedding,
    postgresql_using='hnsw',
    postgresql_ops={'embedding': 'vector_ip_ops'},
)
Index('ix_rag_results_search_mode', rag_results.c.search_mode)
Index('ix_rag_results_success', rag_results.c.success)
Index('ix_chat_messages_session_id', chat_messages.c.session_id)
Index('ix_chat_feedback_message_id', chat_feedback.c.message_id)
Index('ix_llm_usage_events_rag_run_id', llm_usage_events.c.rag_run_id)
Index('ix_llm_usage_events_judge_run_id', llm_usage_events.c.judge_run_id)

__all__ = [
    'document_chunks',
    'documents',
    'embedding_models',
    'llm_model_pricing',
    'llm_usage_events',
    'metadata',
]
