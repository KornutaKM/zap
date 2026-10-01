import asyncio

from app.domain import Vehicle
from app.providers import MockProvider
from app.search_service import deserialize_candidate, serialize_candidate


def test_mock_provider_returns_multiple_store_offers_per_part():
    provider = MockProvider()
    offers = asyncio.run(
        provider.search(Vehicle("BMW", "X3 G01", 2020), "передние колодки")
    )
    ate = [item for item in offers if item.article == "13.0460-7184.2"]
    assert len(ate) == 3
    assert {item.provider for item in ate} == {
        "Exist demo",
        "Autodoc demo",
        "Emex demo",
    }


def test_candidate_serialization_roundtrip():
    provider = MockProvider()
    offers = asyncio.run(
        provider.search(Vehicle("BMW", "X3 G01", 2020), "масляный фильтр")
    )
    from app.domain import group_offers

    candidate = group_offers(offers)[0]
    restored = deserialize_candidate(serialize_candidate(candidate))

    assert restored.article == candidate.article
    assert restored.brand == candidate.brand
    assert len(restored.offers) == len(candidate.offers)
    assert restored.min_price == candidate.min_price
