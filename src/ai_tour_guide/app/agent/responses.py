"""Shared user-facing agent responses."""

INSUFFICIENT_CONTEXT_ANSWER = (
    'The available sources do not contain enough information to answer that question.'
)
NO_BACKEND_AVAILABLE_ANSWER = 'No backend is available for this service.'
LLM_CONFIGURATION_REQUIRED_ANSWER = (
    'An LLM configuration is required for the application to function.'
)
__all__ = [
    'INSUFFICIENT_CONTEXT_ANSWER',
    'LLM_CONFIGURATION_REQUIRED_ANSWER',
    'NO_BACKEND_AVAILABLE_ANSWER',
]
