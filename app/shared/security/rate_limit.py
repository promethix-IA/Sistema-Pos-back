from threading import Lock
from time import monotonic

from fastapi import Request

from shared.config.settings import settings
from shared.exceptions import RateLimitError


class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = monotonic()
        with self._lock:
            stamps = [stamp for stamp in self._hits.get(key, []) if now - stamp < self.window_seconds]
            if len(stamps) >= self.max_attempts:
                self._hits[key] = stamps
                raise RateLimitError("Demasiados intentos. Espera unos minutos e intenta de nuevo.")
            stamps.append(now)
            self._hits[key] = stamps
            if len(self._hits) > 4000:
                self._hits = {
                    item_key: item_stamps
                    for item_key, item_stamps in self._hits.items()
                    if item_stamps
                }

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


login_limiter = SlidingWindowLimiter(
    max_attempts=settings.login_max_attempts,
    window_seconds=settings.login_window_seconds,
)

ip_limiter = SlidingWindowLimiter(
    max_attempts=max(settings.login_max_attempts * 4, 20),
    window_seconds=settings.login_window_seconds,
)

reset_limiter = SlidingWindowLimiter(
    max_attempts=5,
    window_seconds=settings.login_window_seconds,
)

reset_ip_limiter = SlidingWindowLimiter(
    max_attempts=20,
    window_seconds=settings.login_window_seconds,
)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
