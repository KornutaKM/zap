import asyncio

from app.rate_limit import MemoryRateLimiter, UnlimitedRateLimiter


def test_memory_rate_limiter_blocks_after_limit():
    limiter = MemoryRateLimiter(limit=2, window_seconds=60)
    first = asyncio.run(limiter.check(42))
    second = asyncio.run(limiter.check(42))
    third = asyncio.run(limiter.check(42))

    assert first.allowed
    assert second.allowed
    assert not third.allowed
    assert third.retry_after_seconds > 0


def test_rate_limits_are_per_user():
    limiter = MemoryRateLimiter(limit=1, window_seconds=60)
    assert asyncio.run(limiter.check(1)).allowed
    assert not asyncio.run(limiter.check(1)).allowed
    assert asyncio.run(limiter.check(2)).allowed


def test_unlimited_limiter_never_blocks():
    limiter = UnlimitedRateLimiter()
    for _ in range(20):
        assert asyncio.run(limiter.check(1)).allowed
