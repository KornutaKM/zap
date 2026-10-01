import asyncio
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class MemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self._state: dict[int, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, user_id: int) -> RateLimitDecision:
        now = time.monotonic()
        async with self._lock:
            count, reset_at = self._state.get(
                user_id,
                (0, now + self.window_seconds),
            )
            if reset_at <= now:
                count = 0
                reset_at = now + self.window_seconds

            count += 1
            self._state[user_id] = (count, reset_at)
            if count <= self.limit:
                return RateLimitDecision(True)

            retry = max(1, int(reset_at - now))
            return RateLimitDecision(False, retry)


class RedisRateLimiter:
    def __init__(self, redis_url: str, limit: int, window_seconds: int) -> None:
        from redis.asyncio import Redis

        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)

    async def check(self, user_id: int) -> RateLimitDecision:
        key = f"zap:rate:{user_id}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.window_seconds)

        if count <= self.limit:
            return RateLimitDecision(True)

        ttl = await self.redis.ttl(key)
        return RateLimitDecision(False, max(1, int(ttl)))


class UnlimitedRateLimiter:
    async def check(self, user_id: int) -> RateLimitDecision:
        return RateLimitDecision(True)


def build_rate_limiter(
    backend: str,
    *,
    limit: int,
    window_seconds: int,
    redis_url: str | None,
):
    mode = backend.casefold().strip()
    if mode in {"off", "disabled", "none"}:
        return UnlimitedRateLimiter()
    if mode == "memory":
        return MemoryRateLimiter(limit, window_seconds)
    if mode == "redis":
        if not redis_url:
            raise ValueError("REDIS_URL is required when RATE_LIMIT_BACKEND=redis")
        return RedisRateLimiter(redis_url, limit, window_seconds)
    raise ValueError("RATE_LIMIT_BACKEND must be memory, redis or off")
