import asyncio

from app.domain import Vehicle
from app.providers import PartsProvider
from app.search_service import PartsSearchService


class FailingProvider(PartsProvider):
    name = "broken"

    def __init__(self):
        self.calls = 0

    async def search(self, vehicle: Vehicle, query: str):
        self.calls += 1
        raise RuntimeError("boom")


class HealthyProvider(PartsProvider):
    name = "healthy"

    async def search(self, vehicle: Vehicle, query: str):
        return []


def test_circuit_breaker_stops_repeated_failed_calls():
    provider = FailingProvider()
    service = PartsSearchService(
        [provider],
        cache_ttl_seconds=0,
        circuit_failure_threshold=2,
        circuit_cooldown_seconds=60,
    )
    vehicle = Vehicle("BMW", "X3", 2020)

    asyncio.run(service.raw_offers(vehicle, "a"))
    asyncio.run(service.raw_offers(vehicle, "b"))
    asyncio.run(service.raw_offers(vehicle, "c"))

    assert provider.calls == 2
    status = service.provider_statuses()[0]
    assert status["state"] == "open"
    assert status["failures"] == 2
    assert status["retry_after_seconds"] > 0


def test_successful_provider_is_healthy():
    service = PartsSearchService([HealthyProvider()], cache_ttl_seconds=0)
    asyncio.run(service.raw_offers(Vehicle("BMW", "X3", 2020), "x"))
    status = service.provider_statuses()[0]
    assert status["state"] == "healthy"
    assert status["successes"] == 1
    assert status["failures"] == 0
