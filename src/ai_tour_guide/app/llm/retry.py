"""Shared retry policy for transient language-model provider failures."""

import asyncio
from collections.abc import Awaitable, Callable

LLM_RETRY_MAX_ATTEMPTS = 3
LLM_RETRY_BASE_DELAY_SECONDS = 0.5
LLM_RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})


def is_retryable_provider_error(exc: Exception) -> bool:
    """Return whether a provider exception may succeed on a later attempt."""
    status_code = getattr(exc, 'status_code', None)
    return status_code is None or status_code in LLM_RETRYABLE_STATUS_CODES


async def retry_provider_call[Result](
    operation: Callable[[], Awaitable[Result]],
    *,
    is_retryable: Callable[[Exception], bool] = is_retryable_provider_error,
) -> Result:
    """Run a provider call with bounded exponential backoff."""
    for attempt in range(LLM_RETRY_MAX_ATTEMPTS):
        try:
            return await operation()
        except Exception as exc:
            if attempt == LLM_RETRY_MAX_ATTEMPTS - 1 or not is_retryable(exc):
                raise
            delay = LLM_RETRY_BASE_DELAY_SECONDS * (2**attempt)
            await asyncio.sleep(delay)
    raise AssertionError('retry loop exited without returning or raising')


__all__ = [
    'LLM_RETRYABLE_STATUS_CODES',
    'LLM_RETRY_BASE_DELAY_SECONDS',
    'LLM_RETRY_MAX_ATTEMPTS',
    'is_retryable_provider_error',
    'retry_provider_call',
]
