"""Async rate limiting for outbound language-model requests."""

import asyncio
from time import monotonic

DEFAULT_REQUESTS_PER_SECOND = 5.0


class AsyncRateLimiter:
    """Allow at most a configured number of requests to start per second."""

    def __init__(
        self, requests_per_second: float = DEFAULT_REQUESTS_PER_SECOND
    ) -> None:
        if requests_per_second <= 0:
            raise ValueError('requests_per_second must be greater than zero')
        self._interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._last_request_at: float | None = None

    async def acquire(self) -> None:
        """Wait until the next request may start."""
        async with self._lock:
            now = monotonic()
            if self._last_request_at is not None:
                delay = self._interval - (now - self._last_request_at)
                if delay > 0:
                    await asyncio.sleep(delay)
            self._last_request_at = monotonic()


__all__ = ['DEFAULT_REQUESTS_PER_SECOND', 'AsyncRateLimiter']
