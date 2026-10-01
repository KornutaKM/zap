from decimal import Decimal

from app.domain import Offer, PartCandidate
from app.procurement import PurchaseRequest, optimize_purchase


def candidate(article, prices):
    offers = tuple(
        Offer(store, "Brand", article, "Part", Decimal(price), days, .9)
        for store, price, days in prices
    )
    return PartCandidate("Brand", article, "Part", .9, offers)


def test_optimizer_can_prefer_one_store_after_shipping():
    requests = [
        PurchaseRequest("Brand", "A", "Part A"),
        PurchaseRequest("Brand", "B", "Part B"),
    ]
    candidates = {
        ("brand", "a"): candidate("A", [("S1", "1000", 1), ("S2", "1200", 2)]),
        ("brand", "b"): candidate("B", [("S1", "1500", 1), ("S2", "1000", 2)]),
    }

    plans = optimize_purchase(
        requests,
        candidates,
        shipping_fee=Decimal("700"),
        free_threshold=Decimal("999999"),
    )

    assert plans
    best = plans[0]
    assert best.provider_count == 1
    assert best.grand_total == Decimal("3200")


def test_optimizer_multiplies_quantity():
    requests = [PurchaseRequest("Brand", "A", "Part A", quantity=2)]
    candidates = {
        ("brand", "a"): candidate("A", [("S1", "1000", 1)]),
    }
    plans = optimize_purchase(
        requests,
        candidates,
        shipping_fee=Decimal("0"),
    )
    assert plans[0].item_total == Decimal("2000")
