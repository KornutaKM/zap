from dataclasses import dataclass
from decimal import Decimal

@dataclass(slots=True, frozen=True)
class Vehicle:
    brand: str
    model: str
    year: int
    vin: str | None = None

@dataclass(slots=True, frozen=True)
class Offer:
    provider: str
    brand: str
    article: str
    title: str
    price: Decimal
    delivery_days: int
    quality: float

def rank_offers(offers: list[Offer]) -> dict[str, Offer] | None:
    if not offers:
        return None
    cheapest = min(offers, key=lambda x: (x.price, x.delivery_days))
    fastest = min(offers, key=lambda x: (x.delivery_days, x.price))
    lo, hi = min(x.price for x in offers), max(x.price for x in offers)
    max_days = max(max(x.delivery_days, 1) for x in offers)

    def score(x: Offer) -> float:
        price_score = 1.0 if lo == hi else 1.0 - float((x.price - lo) / (hi - lo))
        speed_score = 1.0 - ((x.delivery_days - 1) / max_days)
        return 0.50 * x.quality + 0.30 * price_score + 0.20 * speed_score

    best = max(offers, key=score)
    return {"best": best, "cheapest": cheapest, "fastest": fastest}
