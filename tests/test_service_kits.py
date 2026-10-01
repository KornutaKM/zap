from decimal import Decimal

from app.domain import Offer, PartCandidate
from app.service_kits import BuiltKit, KitItem, SERVICE_KITS


def candidate(article: str, price: str, days: int) -> PartCandidate:
    offer = Offer("Store", "Brand", article, "Part", Decimal(price), days, .9)
    return PartCandidate("Brand", article, "Part", .9, (offer,))


def test_built_kit_total_and_delivery():
    kit = BuiltKit(
        SERVICE_KITS["basic_to"],
        (
            KitItem("a", candidate("1", "1000", 1)),
            KitItem("b", candidate("2", "2000", 3)),
            KitItem("c", candidate("3", "500", 2)),
        ),
    )
    assert kit.total_price == Decimal("3500")
    assert kit.max_delivery_days == 3


def test_front_brakes_has_two_queries():
    assert len(SERVICE_KITS["front_brakes"].queries) == 2
