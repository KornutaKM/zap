import asyncio
from decimal import Decimal

from app.domain import Offer, PriceAlert, Vehicle
from app.price_alerts import current_article_price
from app.providers import PartsProvider
from app.search_service import PartsSearchService


class ArticleProvider(PartsProvider):
    name = "test"

    async def search(self, vehicle: Vehicle, query: str) -> list[Offer]:
        return [
            Offer("A", "ATE", "13.0460-7184.2", "Pads", Decimal("100"), 2, .9),
            Offer("B", "ATE", "13046071842", "Pads", Decimal("90"), 3, .9),
            Offer("C", "TRW", "OTHER", "Pads", Decimal("50"), 1, .9),
        ]


def test_current_article_price_normalizes_punctuation():
    service = PartsSearchService([ArticleProvider()])
    price = asyncio.run(
        current_article_price(
            service,
            Vehicle("BMW", "X3", 2020),
            "13.0460-7184.2",
        )
    )
    assert price == Decimal("90")


def test_price_alert_domain_threshold():
    alert = PriceAlert(
        id=1,
        telegram_user_id=10,
        brand="ATE",
        article="123",
        title="Pads",
        target_price=Decimal("100"),
        last_price=Decimal("120"),
    )
    assert alert.target_price < alert.last_price
