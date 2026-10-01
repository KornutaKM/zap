import asyncio

from app.domain import Offer, PartCandidate, Vehicle, group_offers, rank_parts
from app.providers import PartsProvider


class PartsSearchService:
    def __init__(self, providers: list[PartsProvider]) -> None:
        self.providers = providers

    async def raw_offers(self, vehicle: Vehicle | None, query: str) -> list[Offer]:
        provider_vehicle = vehicle or Vehicle("Автомобиль", "не выбран", 0, None)
        batches = await asyncio.gather(
            *(provider.search(provider_vehicle, query) for provider in self.providers),
            return_exceptions=True,
        )

        offers: list[Offer] = []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            offers.extend(batch)
        return offers

    async def parts(self, vehicle: Vehicle | None, query: str) -> list[PartCandidate]:
        offers = await self.raw_offers(vehicle, query)
        return rank_parts(group_offers(offers))


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
