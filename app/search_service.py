import asyncio
import time

from app.domain import Offer, PartCandidate, Vehicle, group_offers, rank_parts
from app.providers import PartsProvider


class PartsSearchService:
    def __init__(
        self,
        providers: list[PartsProvider],
        cache_ttl_seconds: float = 60.0,
        provider_timeout_seconds: float = 5.0,
    ) -> None:
        self.providers = providers
        self.cache_ttl_seconds = cache_ttl_seconds
        self.provider_timeout_seconds = provider_timeout_seconds
        self._cache: dict[tuple, tuple[float, tuple[Offer, ...]]] = {}

    @staticmethod
    def _cache_key(vehicle: Vehicle | None, query: str) -> tuple:
        return (
            vehicle.brand.casefold() if vehicle else None,
            vehicle.model.casefold() if vehicle else None,
            vehicle.year if vehicle else None,
            vehicle.vin if vehicle else None,
            " ".join(query.casefold().split()),
        )

    async def _provider_search(
        self,
        provider: PartsProvider,
        vehicle: Vehicle,
        query: str,
    ) -> list[Offer]:
        try:
            return await asyncio.wait_for(
                provider.search(vehicle, query),
                timeout=self.provider_timeout_seconds,
            )
        except (TimeoutError, Exception):
            return []

    async def raw_offers(self, vehicle: Vehicle | None, query: str) -> list[Offer]:
        key = self._cache_key(vehicle, query)
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached is not None and cached[0] > now:
            return list(cached[1])

        provider_vehicle = vehicle or Vehicle("Автомобиль", "не выбран", 0, None)
        batches = await asyncio.gather(
            *(
                self._provider_search(provider, provider_vehicle, query)
                for provider in self.providers
            )
        )

        offers = [offer for batch in batches for offer in batch]
        self._cache[key] = (
            now + self.cache_ttl_seconds,
            tuple(offers),
        )
        return offers

    async def parts(self, vehicle: Vehicle | None, query: str) -> list[PartCandidate]:
        offers = await self.raw_offers(vehicle, query)
        return rank_parts(group_offers(offers))

    def clear_cache(self) -> None:
        self._cache.clear()


def serialize_candidate(candidate: PartCandidate) -> dict:
    return {
        "brand": candidate.brand,
        "article": candidate.article,
        "title": candidate.title,
        "quality": candidate.quality,
        "offers": [
            {
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
            for offer in candidate.offers
        ],
    }


def deserialize_candidate(data: dict) -> PartCandidate:
    from decimal import Decimal

    offers = tuple(
        Offer(
            provider=item["provider"],
            brand=item["brand"],
            article=item["article"],
            title=item["title"],
            price=Decimal(item["price"]),
            delivery_days=item["delivery_days"],
            quality=item["quality"],
            url=item.get("url"),
            in_stock=item.get("in_stock", True),
        )
        for item in data["offers"]
    )
    return PartCandidate(
        brand=data["brand"],
        article=data["article"],
        title=data["title"],
        quality=data["quality"],
        offers=offers,
    )
