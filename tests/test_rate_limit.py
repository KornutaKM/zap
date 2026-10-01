import asyncio

from app.rate_limit import MemoryRateLimiter, UnlimitedRateLimiter


async def _check_three(limiter):
    first = await limiter.check(42)
    second = await limiter.check(42)
    third = await limiter.check(42)
    return first, second, third


def test_memory_rate_limiter_blocks_after_limit():
    limiter = MemoryRateLimiter(limit=2, window_seconds=60)
    first, second, third = asyncio.run(_check_three(limiter))

    assert first.allowed
    assert second.allowed
    assert not third.allowed
    assert third.retry_after_seconds > 0


async def _per_user(limiter):
    return (
        await limiter.check(1),
        await limiter.check(1),
        await limiter.check(2),
    )


def test_rate_limits_are_per_user():
    limiter = MemoryRateLimiter(limit=1, window_seconds=60)
    first, second, other = asyncio.run(_per_user(limiter))
    assert first.allowed
    assert not second.allowed
    assert other.allowed


async def _many_unlimited(limiter):
    return [await limiter.check(1) for _ in range(20)]


def test_unlimited_limiter_never_blocks():
    limiter = UnlimitedRateLimiter()
    assert all(item.allowed for item in asyncio.run(_many_unlimited(limiter)))
