import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from decimal import Decimal

from app.domain import Offer


class SearchCache(ABC):
    @abstractmethod
    async def get(self, key: str) -> list[Offer] | None:
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: str, offers: list[Offer], ttl_seconds: float) -> None:
        raise NotImplementedError

    async def clear(self) -> None:
        return None


def build_cache_key(parts: tuple[object, ...]) -> str:
    raw = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"zap:search:{digest}"


def _serialize_offer(offer: Offer) -> dict:
    return {
        "provider": offer.provider,
        "brand": offer.brand,
        "article": offer.article,
        "title": offer.title,
        "price": str(offer.price),
        "delivery_days": offer.delivery_days,
        "quality": offer.quality,
        "url": offer.url,
        "in_stock": offer.in_stock,
    }


def _deserialize_offer(item: dict) -> Offer:
    return Offer(
        provider=item["provider"],
        brand=item["brand"],
        article=item["article"],
        title=item["title"],
        price=Decimal(item["price"]),
        delivery_days=int(item["delivery_days"]),
        quality=float(item["quality"]),
        url=item.get("url"),
        in_stock=bool(item.get("in_stock", True)),
    )


class MemorySearchCache(SearchCache):
    def __init__(self) -> None:
        self._values: dict[str, tuple[float, tuple[Offer, ...]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> list[Offer] | None:
        now = time.monotonic()
        async with self._lock:
            cached = self._values.get(key)
            if cached is None:
                return None
            expires_at, offers = cached
            if expires_at <= now:
                self._values.pop(key, None)
                return None
            return list(offers)

    async def set(self, key: str, offers: list[Offer], ttl_seconds: float) -> None:
        async with self._lock:
            self._values[key] = (
                time.monotonic() + max(0.0, ttl_seconds),
                tuple(offers),
            )

    async def clear(self) -> None:
        async with self._lock:
            self._values.clear()


class RedisSearchCache(SearchCache):
    def __init__(self, redis_url: str) -> None:
        from redis.asyncio import Redis

        self.redis = Redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> list[Offer] | None:
        raw = await self.redis.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                return None
            return [_deserialize_offer(item) for item in data if isinstance(item, dict)]
        except (TypeError, ValueError, KeyError):
            await self.redis.delete(key)
            return None

    async def set(self, key: str, offers: list[Offer], ttl_seconds: float) -> None:
        payload = json.dumps(
            [_serialize_offer(item) for item in offers],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        ttl = max(1, int(ttl_seconds))
        await self.redis.set(key, payload, ex=ttl)

    async def clear(self) -> None:
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor,
                match="zap:search:*",
                count=200,
            )
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break


def build_search_cache(backend: str, redis_url: str | None) -> SearchCache:
    mode = backend.casefold().strip()
    if mode == "memory":
        return MemorySearchCache()
    if mode == "redis":
        if not redis_url:
            raise ValueError("REDIS_URL is required when SEARCH_CACHE_BACKEND=redis")
        return RedisSearchCache(redis_url)
    raise ValueError("SEARCH_CACHE_BACKEND must be 'memory' or 'redis'")
