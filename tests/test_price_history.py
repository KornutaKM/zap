from decimal import Decimal

from app.domain import PriceHistoryPoint
from app.price_history import summarize_price_history


def point(provider, price, idx):
    return PriceHistoryPoint(
        id=idx,
        provider=provider,
        brand="ATE",
        article="123",
        price=Decimal(str(price)),
        delivery_days=2,
        observed_at=f"2026-10-01T10:0{idx}:00",
    )


def test_price_history_summary_shows_direction_and_range():
    text = summarize_price_history([
        point("Store", 900, 3),
        point("Store", 1000, 2),
        point("Store", 1200, 1),
    ])
    assert "↓" in text
    assert "900" in text
    assert "1 200" in text
    assert "точек: 3" in text


def test_empty_price_history():
    assert "не накоплена" in summarize_price_history([])
