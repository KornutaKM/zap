from decimal import Decimal
from app.domain import Offer, rank_offers

def test_ranking():
    offers = [
        Offer("A", "Premium", "1", "Part", Decimal("100"), 3, .98),
        Offer("B", "Value", "2", "Part", Decimal("70"), 2, .88),
        Offer("C", "Budget", "3", "Part", Decimal("50"), 5, .55),
        Offer("D", "Fast", "4", "Part", Decimal("90"), 1, .90),
    ]
    ranked = rank_offers(offers)
    assert ranked["cheapest"].article == "3"
    assert ranked["fastest"].article == "4"
    assert ranked["best"].article in {"1", "2", "4"}
