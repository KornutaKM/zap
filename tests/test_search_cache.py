import asyncio
from decimal import Decimal

from app.domain import Offer, Vehicle
from app.providers import PartsProvider
from app.search_service import PartsSearchService


class CountingProvider(PartsProvider):
    name = "counting"

    def __init__(self):
        self.calls = 0

    async def search(self, vehicle: Vehicle, query: str) -> list[Offer]:
        self.calls += 1
        return [
            Offer(
                provider=self.name,
                brand="Brand",
                article="A1",
                title="Part",
                price=Decimal("100"),
                delivery_days=1,
                quality=.9,
            )
        ]


def test_search_service_uses_ttl_cache():
    provider = CountingProvider()
    service = PartsSearchService([provider], cache_ttl_seconds=60)
    vehicle = Vehicle("BMW", "X3", 2020)

    asyncio.run(service.parts(vehicle, "filter"))
    asyncio.run(service.parts(vehicle, "filter"))

    assert provider.calls == 1


def test_cache_key_normalizes_query_spacing_and_case():
    provider = CountingProvider()
    service = PartsSearchService([provider], cache_ttl_seconds=60)
    vehicle = Vehicle("BMW", "X3", 2020)

    asyncio.run(service.parts(vehicle, " Oil   Filter "))
    asyncio.run(service.parts(vehicle, "oil filter"))

    assert provider.calls == 1
