"""Global async token-bucket rate limiter (one instance shared by all MB fetchers)."""
import asyncio
import time


class RateLimiter:
    def __init__(self, rate_per_sec: float):
        self.min_interval = 1.0 / rate_per_sec
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def acquire(self):
        # Serializes callers >= min_interval apart. The sleep here is the
        # "dead time" that concurrent Claude workers run inside.
        async with self._lock:
            now = time.monotonic()
            wait = self._next - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next = now + self.min_interval
