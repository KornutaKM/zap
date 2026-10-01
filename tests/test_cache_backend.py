import asyncio
from decimal import Decimal

from app.cache_backend import MemorySearchCache, build_cache_key
from app.domain import Offer


def sample_offer() -> Offer:
    return Offer(
        provider="Store",
        brand="ATE",
        article="123",
        title="Pads",
        price=Decimal("100.50"),
        delivery_days=2,
        quality=.9,
    )


def test_memory_cache_roundtrip():
    cache = MemorySearchCache()
    key = build_cache_key(("BMW", "X3", 2020, "pads"))
    asyncio.run(cache.set(key, [sample_offer()], 60))
    result = asyncio.run(cache.get(key))
    assert result is not None
    assert result[0].article == "123"
    assert result[0].price == Decimal("100.50")


def test_cache_key_is_stable_and_namespaced():
    one = build_cache_key(("BMW", "X3", 2020, "pads"))
    two = build_cache_key(("BMW", "X3", 2020, "pads"))
    three = build_cache_key(("BMW", "X3", 2020, "discs"))
    assert one == two
    assert one != three
    assert one.startswith("zap:search:")
