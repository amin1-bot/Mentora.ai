"""Simple per-IP rate limiting for signup and login.

Limitation: counts live in this process's memory, so with several server copies each
copy counts separately. The blueprint moves this to Redis in Phase 13. Account lockout
after repeated wrong passwords is stored in the database and works across copies.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import TooManyRequests


class SlidingWindowLimiter:
    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str, limit: int) -> bool:
        """Record one attempt. Returns False if the key is over its limit."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


auth_limiter = SlidingWindowLimiter()


def limit_auth_attempts(request: Request) -> None:
    """FastAPI dependency for signup and login routes."""
    ip = request.client.host if request.client else "unknown"
    key = f"{request.url.path}:{ip}"
    if not auth_limiter.hit(key, get_settings().auth_rate_limit_per_minute):
        raise TooManyRequests()
