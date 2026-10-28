"""Per-visitor rate limiting inside a service.

The gateway (Traefik) does this when there is one. On hosts without it (Render's free plan,
behind Netlify's proxy) the services do it themselves: a sliding window of requests per
visitor address, kept in memory. It is meant for a single instance of each service.
"""

import time
from collections import deque
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request

from py_common.errors import TooManyRequestsError

# Visitors seen in the last window are kept; beyond this many, the oldest are forgotten.
MAX_TRACKED_VISITORS = 10_000


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits.pop(key, None) or deque()
        while hits and hits[0] <= now - self._window:
            hits.popleft()
        allowed = len(hits) < self._limit
        if allowed:
            hits.append(now)
        # Re-inserted at the end: the dict stays ordered from least to most recently seen.
        self._hits[key] = hits
        if len(self._hits) > MAX_TRACKED_VISITORS:
            del self._hits[next(iter(self._hits))]
        return allowed


def client_address(request: Request) -> str:
    """The visitor's address, as reported by the proxy in front of the service.

    Netlify sends it in x-nf-client-connection-ip; other proxies put it first in
    X-Forwarded-For. Without a proxy, the address of the connection is used.
    """
    netlify = request.headers.get("x-nf-client-connection-ip", "").strip()
    if netlify:
        return netlify
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def rate_limit_dependency(
    get_limiter: Callable[[Request], RateLimiter | None],
) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """FastAPI dependency that answers 429 when a visitor goes over the limit.

    `get_limiter` returns the limiter of the app handling the request, or None when rate
    limiting is off (each app keeps its own counters).
    """

    async def check(request: Request) -> None:
        limiter = get_limiter(request)
        if limiter is not None and not limiter.allow(client_address(request)):
            raise TooManyRequestsError()

    return check
