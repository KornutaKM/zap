from decimal import Decimal

from app.domain import Offer, PartCandidate
from app.procurement import (
    ProviderCommercialRule,
    PurchaseRequest,
    optimize_purchase,
)


def candidate(article, offers):
    return PartCandidate(
        "Brand",
        article,
        "Part",
        .9,
        tuple(
            Offer(store, "Brand", article, "Part", Decimal(price), days, .9)
            for store, price, days in offers
        ),
    )


def test_provider_specific_shipping_changes_best_plan():
    requests = [
        PurchaseRequest("Brand", "A", "A"),
        PurchaseRequest("Brand", "B", "B"),
    ]
    candidates = {
        ("brand", "a"): candidate("A", [("Fast", "1000", 1), ("CheapShip", "1100", 2)]),
        ("brand", "b"): candidate("B", [("Fast", "1000", 1), ("CheapShip", "1100", 2)]),
    }
    rules = {
        "fast": ProviderCommercialRule(
            shipping_fee=Decimal("1000"),
            free_threshold=Decimal("999999"),
        ),
        "cheapship": ProviderCommercialRule(
            shipping_fee=Decimal("0"),
            free_threshold=Decimal("0"),
        ),
    }

    plans = optimize_purchase(
        requests,
        candidates,
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
        provider_rules=rules,
    )

    assert plans[0].grand_total == Decimal("2200")
    assert all(choice.offer.provider == "CheapShip" for choice in plans[0].choices)
