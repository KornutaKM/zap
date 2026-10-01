from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class Vehicle:
    brand: str
    model: str
    year: int
    vin: str | None = None
    id: int | None = None
    generation_code: str | None = None
    engine: str | None = None
    fuel: str | None = None
    drive: str | None = None
    power_hp: int | None = None
    modification_key: str | None = None


@dataclass(slots=True, frozen=True)
class SearchHistoryItem:
    id: int
    query: str
    vehicle_label: str | None = None


@dataclass(slots=True, frozen=True)
class FavoritePart:
    id: int
    brand: str
    article: str
    title: str


@dataclass(slots=True, frozen=True)
class PriceAlert:
    id: int
    telegram_user_id: int
    brand: str
    article: str
    title: str
    target_price: Decimal
    last_price: Decimal | None = None
    vehicle_id: int | None = None
    is_active: bool = True


@dataclass(slots=True, frozen=True)
class ShoppingListItem:
    id: int
    telegram_user_id: int
    brand: str
    article: str
    title: str
    quantity: int = 1
    vehicle_id: int | None = None


@dataclass(slots=True, frozen=True)
class Offer:
    provider: str
    brand: str
    article: str
    title: str
    price: Decimal
    delivery_days: int
    quality: float
    url: str | None = None
    in_stock: bool = True


@dataclass(slots=True, frozen=True)
class PartCandidate:
    brand: str
    article: str
    title: str
    quality: float
    offers: tuple[Offer, ...]
    fitment_status: str = "unverified"
    oe_numbers: tuple[str, ...] = ()
    fitment_reason: str = ""

    @property
    def cheapest_offer(self) -> Offer:
        return min(self.offers, key=lambda x: (x.price, x.delivery_days))

    @property
    def fastest_offer(self) -> Offer:
        return min(self.offers, key=lambda x: (x.delivery_days, x.price))

    @property
    def min_price(self) -> Decimal:
        return self.cheapest_offer.price

    @property
    def min_delivery_days(self) -> int:
        return self.fastest_offer.delivery_days


def rank_offers(offers: list[Offer]) -> dict[str, Offer] | None:
    if not offers:
        return None

    available = [item for item in offers if item.in_stock] or offers
    cheapest = min(available, key=lambda x: (x.price, x.delivery_days))
    fastest = min(available, key=lambda x: (x.delivery_days, x.price))
    lo, hi = min(x.price for x in available), max(x.price for x in available)
    max_days = max(max(x.delivery_days, 1) for x in available)

    def score(x: Offer) -> float:
        price_score = 1.0 if lo == hi else 1.0 - float((x.price - lo) / (hi - lo))
        speed_score = 1.0 - ((x.delivery_days - 1) / max_days)
        return 0.50 * x.quality + 0.30 * price_score + 0.20 * speed_score

    best = max(available, key=score)
    return {"best": best, "cheapest": cheapest, "fastest": fastest}


def group_offers(offers: list[Offer]) -> list[PartCandidate]:
    groups: dict[tuple[str, str], list[Offer]] = {}
    for offer in offers:
        key = (offer.brand.casefold(), offer.article.casefold())
        groups.setdefault(key, []).append(offer)

    candidates = [
        PartCandidate(
            brand=items[0].brand,
            article=items[0].article,
            title=items[0].title,
            quality=max(item.quality for item in items),
            offers=tuple(sorted(items, key=lambda x: (x.price, x.delivery_days))),
        )
        for items in groups.values()
    ]
    return candidates


def rank_parts(candidates: list[PartCandidate]) -> list[PartCandidate]:
    if not candidates:
        return []

    min_price = min(item.min_price for item in candidates)
    max_price = max(item.min_price for item in candidates)
    max_days = max(max(item.min_delivery_days, 1) for item in candidates)

    def score(item: PartCandidate) -> float:
        if min_price == max_price:
            price_score = 1.0
        else:
            price_score = 1.0 - float(
                (item.min_price - min_price) / (max_price - min_price)
            )
        speed_score = 1.0 - ((item.min_delivery_days - 1) / max_days)
        return 0.55 * item.quality + 0.30 * price_score + 0.15 * speed_score

    return sorted(
        candidates,
        key=lambda item: (score(item), -float(item.min_price)),
        reverse=True,
    )
