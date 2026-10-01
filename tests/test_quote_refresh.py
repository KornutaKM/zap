from decimal import Decimal

from app.domain import Offer
from app.procurement import (
    PurchaseChoice,
    PurchasePlan,
    PurchaseRequest,
    compare_purchase_plans,
    requests_from_plan,
)
from app.ui import purchase_comparison_text, quote_refresh_keyboard


def plan(total: str, provider_count: int, days: int) -> PurchasePlan:
    request = PurchaseRequest("ATE", "123", "Pads", 1)
    offer = Offer(
        "Store",
        "ATE",
        "123",
        "Pads",
        Decimal(total),
        days,
        .9,
        url="https://shop.example/123",
    )
    return PurchasePlan(
        mode="optimized",
        title="Plan",
        choices=(PurchaseChoice(request, offer),),
        item_total=Decimal(total),
        shipping_total=Decimal("0"),
        grand_total=Decimal(total),
        provider_count=provider_count,
        max_delivery_days=days,
    )


def test_quote_comparison_detects_price_drop():
    saved = plan("1200", 1, 3)
    current = plan("900", 1, 2)

    comparison = compare_purchase_plans(saved, current)

    assert comparison.delta == Decimal("-300")
    assert comparison.delta_percent == Decimal("-25")
    text = purchase_comparison_text(comparison, current)
    assert "дешевле" in text
    assert "25.0%" in text


def test_requests_from_plan_deduplicates_articles():
    base = plan("1000", 1, 2)
    duplicated = PurchasePlan(
        mode=base.mode,
        title=base.title,
        choices=base.choices + base.choices,
        item_total=Decimal("2000"),
        shipping_total=Decimal("0"),
        grand_total=Decimal("2000"),
        provider_count=1,
        max_delivery_days=2,
    )
    assert len(requests_from_plan(duplicated)) == 1


def test_quote_refresh_keyboard_can_save_new_snapshot():
    current = plan("900", 1, 2)
    markup = quote_refresh_keyboard(7, current, 0)
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert "quote:save:0" in callbacks
    assert "quote:open:7" in callbacks
