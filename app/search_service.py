import asyncio
import time

from dataclasses import replace

from app.domain import Offer, PartCandidate, Vehicle, group_offers, rank_parts
from app.fitment import FitmentCatalog, FitmentResolution
from app.providers import PartsProvider


class PartsSearchService:
    def __init__(
        self,
        providers: list[PartsProvider],
        cache_ttl_seconds: float = 60.0,
        provider_timeout_seconds: float = 5.0,
        fitment_catalog: FitmentCatalog | None = None,
    ) -> None:
        self.providers = providers
        self.cache_ttl_seconds = cache_ttl_seconds
        self.provider_timeout_seconds = provider_timeout_seconds
        self.fitment_catalog = fitment_catalog
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
        except Exception:
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
        candidates = rank_parts(group_offers(offers))
        if not candidates or self.fitment_catalog is None:
            return candidates

        resolution = await self.fitment_catalog.resolve(vehicle, query)
        return self._apply_fitment(candidates, resolution)

    @staticmethod
    def _apply_fitment(
        candidates: list[PartCandidate],
        resolution: FitmentResolution,
    ) -> list[PartCandidate]:
        cross_keys = {
            (item.brand.casefold(), item.article.casefold())
            for item in resolution.crosses
        }

        enriched = []
        for candidate in candidates:
            key = (candidate.brand.casefold(), candidate.article.casefold())
            if key in cross_keys:
                enriched.append(
                    replace(
                        candidate,
                        fitment_status=resolution.status,
                        oe_numbers=resolution.oe_numbers,
                        fitment_reason=resolution.reason,
                    )
                )
            else:
                enriched.append(
                    replace(
                        candidate,
                        fitment_status="unverified",
                        oe_numbers=resolution.oe_numbers if resolution.status != "unverified" else (),
                        fitment_reason=(
                            "Артикул не найден среди cross-reference для выбранной применимости."
                            if resolution.status != "unverified"
                            else resolution.reason
                        ),
                    )
                )

        status_rank = {"confirmed": 0, "probable": 1, "unverified": 2}
        return sorted(
            enriched,
            key=lambda item: (
                status_rank.get(item.fitment_status, 3),
                item.min_price,
            ),
        )

    def clear_cache(self) -> None:
        self._cache.clear()


def serialize_candidate(candidate: PartCandidate) -> dict:
    return {
        "brand": candidate.brand,
        "article": candidate.article,
        "title": candidate.title,
        "quality": candidate.quality,
        "fitment_status": candidate.fitment_status,
        "oe_numbers": list(candidate.oe_numbers),
        "fitment_reason": candidate.fitment_reason,
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
        fitment_status=data.get("fitment_status", "unverified"),
        oe_numbers=tuple(data.get("oe_numbers", ())),
        fitment_reason=data.get("fitment_reason", ""),
    )
