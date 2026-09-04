"""Shared user-facing agent responses."""

INSUFFICIENT_CONTEXT_ANSWER = (
    'The available sources do not contain enough information to answer that question.'
)
EMPTY_KNOWLEDGE_BASE_NOTICE = (
    'The language model is configured, but no travel guides have been ingested yet. '
    'Run `make ingest` or use Airflow to add source-grounded travel answers.'
)
GENERATION_ERROR_ANSWER = 'I’m unable to answer this question right now.'
NO_BACKEND_AVAILABLE_ANSWER = 'No backend is available for this service.'
LLM_CONFIGURATION_REQUIRED_ANSWER = (
    'An LLM configuration is required for the application to function.'
)
__all__ = [
    'EMPTY_KNOWLEDGE_BASE_NOTICE',
    'GENERATION_ERROR_ANSWER',
    'INSUFFICIENT_CONTEXT_ANSWER',
    'LLM_CONFIGURATION_REQUIRED_ANSWER',
    'NO_BACKEND_AVAILABLE_ANSWER',
]
