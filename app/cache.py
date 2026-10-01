import hashlib
import json
import time
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis


class CacheBackend(Protocol):
    async def get(self, key: str) -> str | None:
        ...

    async def set(self, key: str, value: str, ttl_seconds: float) -> None:
        ...

    async def close(self) -> None:
        ...


@dataclass
class MemoryCacheBackend:
    _items: dict[str, tuple[float, str]]

    def __init__(self) -> None:
        self._items = {}

    async def get(self, key: str) -> str | None:
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= time.monotonic():
            self._items.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: float) -> None:
        self._items[key] = (time.monotonic() + max(0.0, ttl_seconds), value)

    async def close(self) -> None:
        self._items.clear()


class RedisCacheBackend:
    def __init__(self, url: str, prefix: str = "zap") -> None:
        self.redis = Redis.from_url(url, decode_responses=True)
        self.prefix = prefix.strip(":") or "zap"

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> str | None:
        return await self.redis.get(self._key(key))

    async def set(self, key: str, value: str, ttl_seconds: float) -> None:
        ttl = max(1, int(round(ttl_seconds)))
        await self.redis.set(self._key(key), value, ex=ttl)

    async def close(self) -> None:
        await self.redis.aclose()


def hashed_cache_key(namespace: str, payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"
