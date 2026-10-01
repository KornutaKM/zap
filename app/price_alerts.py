from dataclasses import dataclass
from decimal import Decimal

from app.domain import PriceAlert, Vehicle
from app.search_service import PartsSearchService


@dataclass(frozen=True, slots=True)
class PriceAlertHit:
    alert: PriceAlert
    current_price: Decimal


def _normalize_article(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


async def current_article_price(
    search_service: PartsSearchService,
    vehicle: Vehicle | None,
    article: str,
) -> Decimal | None:
    offers = await search_service.raw_offers(vehicle, article)
    normalized = _normalize_article(article)
    matching = [
        offer
        for offer in offers
        if offer.in_stock and _normalize_article(offer.article) == normalized
    ]
    if not matching:
        return None
    return min(offer.price for offer in matching)


async def check_price_alert(
    alert: PriceAlert,
    search_service: PartsSearchService,
) -> PriceAlertHit | None:
    from app.db import get_vehicle_by_id, update_price_alert

    vehicle = None
    if alert.vehicle_id is not None:
        vehicle = await get_vehicle_by_id(
            alert.telegram_user_id,
            alert.vehicle_id,
        )

    current = await current_article_price(
        search_service,
        vehicle,
        alert.article,
    )
    if current is None:
        return None

    triggered = current <= alert.target_price
    await update_price_alert(
        alert.id,
        last_price=current,
        triggered=triggered,
    )
    if triggered:
        return PriceAlertHit(alert=alert, current_price=current)
    return None


async def check_all_price_alerts(
    search_service: PartsSearchService,
) -> list[PriceAlertHit]:
    from app.db import list_price_alerts

    alerts = await list_price_alerts(active_only=True)
    hits: list[PriceAlertHit] = []
    for alert in alerts:
        hit = await check_price_alert(alert, search_service)
        if hit is not None:
            hits.append(hit)
    return hits
