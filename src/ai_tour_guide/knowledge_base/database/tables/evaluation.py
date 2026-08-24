"""SQLAlchemy Core tables used only by the evaluation schema."""

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

search_evaluation_runs = Table(
    'search_evaluation_runs',
    metadata,
    Column('run_id', UUID(as_uuid=True), primary_key=True),
    Column('dataset_path', Text, nullable=False),
    Column('corpus_path', Text, nullable=False),
    Column('k', Integer, nullable=False),
    Column('status', Text, nullable=False, server_default=text("'running'")),
    Column('configuration', JSONB, nullable=False),
    Column(
        'started_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column('completed_at', DateTime(timezone=True)),
)

search_evaluation_results = Table(
    'search_evaluation_results',
    metadata,
    Column(
        'run_id',
        UUID(as_uuid=True),
        ForeignKey('search_evaluation_runs.run_id', ondelete='CASCADE'),
        nullable=False,
    ),
    Column('mode', Text, nullable=False),
    Column('case_id', Integer, nullable=False),
    Column('category', Text, nullable=False),
    Column('search_latency_ms', Float, nullable=False),
    Column('raw_hit_rate_at_k', Float, nullable=False),
    Column('raw_recall_at_k', Float, nullable=False),
    Column('raw_reciprocal_rank', Float, nullable=False),
    Column('results', JSONB, nullable=False),
    PrimaryKeyConstraint('run_id', 'mode', 'case_id'),
)

rag_evaluation_runs = Table(
    'rag_evaluation_runs',
    metadata,
    Column('run_id', UUID(as_uuid=True), primary_key=True),
    Column('dataset_path', Text, nullable=False),
    Column('corpus_path', Text, nullable=False),
    Column('mode', Text, nullable=False),
    Column('k', Integer, nullable=False),
    Column('status', Text, nullable=False, server_default=text("'completed'")),
    Column('configuration', JSONB, nullable=False),
    Column(
        'started_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column('completed_at', DateTime(timezone=True)),
)

rag_evaluation_results = Table(
    'rag_evaluation_results',
    metadata,
    Column(
        'run_id',
        UUID(as_uuid=True),
        ForeignKey('rag_evaluation_runs.run_id', ondelete='CASCADE'),
        nullable=False,
    ),
    Column(
        'request_id',
        UUID(as_uuid=True),
        # ``rag_results`` belongs to the public metadata registry. The two
        # metadata registries are created independently, so this logical join
        # key cannot be declared as a SQLAlchemy foreign key here.
        nullable=False,
    ),
    Column('case_id', Integer, nullable=False),
    Column('category', Text, nullable=False),
    Column('answerable', Boolean, nullable=False),
    Column('reference_answer', Text),
    Column('expected_source_url', Text),
    Column('expected_source_version', Text),
    Column('expected_section_path', ARRAY(Text)),
    Column('source_precision', Float, nullable=False),
    Column('source_recall', Float, nullable=False),
    Column('section_precision', Float, nullable=False),
    Column('section_recall', Float, nullable=False),
    Column('citation_validity', Float, nullable=False),
    Column('citation_coverage', Float, nullable=False),
    Column('refused', Boolean, nullable=False),
    Column('refusal_correct', Boolean, nullable=False),
    Column('error', Boolean, nullable=False),
    Column('retrieval_latency_ms', Float),
    Column('generation_latency_ms', Float),
    Column('total_latency_ms', Float),
    Column(
        'created_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    PrimaryKeyConstraint('run_id', 'case_id'),
    UniqueConstraint('run_id', 'request_id', name='uq_rag_evaluation_run_request'),
)

Index('ix_search_evaluation_runs_status', search_evaluation_runs.c.status)
Index(
    'ix_search_evaluation_results_mode_case',
    search_evaluation_results.c.mode,
    search_evaluation_results.c.case_id,
)
Index('ix_rag_evaluation_runs_status', rag_evaluation_runs.c.status)
Index(
    'ix_rag_evaluation_results_case',
    rag_evaluation_results.c.case_id,
)
Index(
    'ix_rag_evaluation_results_request_id',
    rag_evaluation_results.c.request_id,
)

rag_judge_runs = Table(
    'rag_judge_runs',
    metadata,
    Column('run_id', UUID(as_uuid=True), primary_key=True),
    Column(
        'rag_run_id',
        UUID(as_uuid=True),
        ForeignKey('rag_evaluation_runs.run_id', ondelete='CASCADE'),
        nullable=False,
    ),
    Column('provider', Text, nullable=False),
    Column('model', Text, nullable=False),
    Column('status', Text, nullable=False, server_default=text("'completed'")),
    Column('configuration', JSONB, nullable=False),
    Column(
        'started_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column('completed_at', DateTime(timezone=True)),
)

rag_judge_results = Table(
    'rag_judge_results',
    metadata,
    Column(
        'run_id',
        UUID(as_uuid=True),
        ForeignKey('rag_judge_runs.run_id', ondelete='CASCADE'),
        nullable=False,
    ),
    Column(
        'request_id',
        UUID(as_uuid=True),
        # ``rag_results`` belongs to the public metadata registry. This is
        # therefore a logical join key, as it is for rag_evaluation_results.
        nullable=False,
    ),
    Column('case_id', Integer, nullable=False),
    Column('answer_correct', Boolean, nullable=False),
    Column('judge_latency_ms', Float, nullable=False),
    Column('judge_reason', Text, nullable=False),
    Column('judge_metadata', JSONB, nullable=False),
    Column(
        'created_at', DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    PrimaryKeyConstraint('run_id', 'case_id'),
    UniqueConstraint('run_id', 'request_id', name='uq_rag_judge_run_request'),
)
Index('ix_rag_judge_runs_rag_run_id', rag_judge_runs.c.rag_run_id)
Index('ix_rag_judge_results_request_id', rag_judge_results.c.request_id)

__all__ = [
    'metadata',
    'rag_evaluation_results',
    'rag_evaluation_runs',
    'rag_judge_results',
    'rag_judge_runs',
    'search_evaluation_results',
    'search_evaluation_runs',
]
