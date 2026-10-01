from decimal import Decimal

from app.domain import Offer, group_offers, rank_parts


def test_group_offers_combines_stores_for_same_part():
    offers = [
        Offer("Store A", "ATE", "123", "Pads", Decimal("100"), 2, .95),
        Offer("Store B", "ATE", "123", "Pads", Decimal("90"), 3, .95),
        Offer("Store A", "TRW", "456", "Pads", Decimal("80"), 2, .90),
    ]

    parts = group_offers(offers)
    ate = next(item for item in parts if item.article == "123")
    assert len(ate.offers) == 2
    assert ate.min_price == Decimal("90")


def test_rank_parts_returns_candidates():
    offers = [
        Offer("A", "Premium", "1", "Part", Decimal("100"), 1, .98),
        Offer("B", "Value", "2", "Part", Decimal("70"), 2, .90),
        Offer("C", "Budget", "3", "Part", Decimal("50"), 4, .50),
    ]
    ranked = rank_parts(group_offers(offers))
    assert len(ranked) == 3
    assert ranked[0].article in {"1", "2"}
