"""SQLAlchemy Core tables used only by the search evaluation schema."""

from sqlalchemy import (
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

Index('ix_search_evaluation_runs_status', search_evaluation_runs.c.status)
Index(
    'ix_search_evaluation_results_mode_case',
    search_evaluation_results.c.mode,
    search_evaluation_results.c.case_id,
)

__all__ = [
    'metadata',
    'search_evaluation_results',
    'search_evaluation_runs',
]
