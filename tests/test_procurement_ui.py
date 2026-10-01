from decimal import Decimal

from app.domain import Offer, PartCandidate, ShoppingListItem
from app.procurement import (
    PurchaseChoice,
    PurchasePlan,
    PurchaseRequest,
    deserialize_purchase_plan,
    serialize_purchase_plan,
)
from app.ui import (
    part_detail_keyboard,
    purchase_plan_keyboard,
    shopping_list_keyboard,
)


def test_purchase_plan_serialization_roundtrip():
    request = PurchaseRequest("ATE", "123", "Pads", 2)
    offer = Offer(
        "Partner",
        "ATE",
        "123",
        "Pads",
        Decimal("1000"),
        2,
        .95,
        url="https://shop.example/item/123",
    )
    plan = PurchasePlan(
        mode="optimized",
        title="Оптимальный заказ",
        choices=(PurchaseChoice(request, offer),),
        item_total=Decimal("2000"),
        shipping_total=Decimal("500"),
        grand_total=Decimal("2500"),
        provider_count=1,
        max_delivery_days=2,
    )

    restored = deserialize_purchase_plan(serialize_purchase_plan(plan))
    assert restored.grand_total == Decimal("2500")
    assert restored.choices[0].request.quantity == 2
    assert restored.choices[0].offer.url == "https://shop.example/item/123"


def test_part_detail_has_shopping_and_provider_deeplink():
    offer = Offer(
        "Partner",
        "ATE",
        "123",
        "Pads",
        Decimal("1000"),
        2,
        .95,
        url="https://shop.example/item/123",
    )
    candidate = PartCandidate("ATE", "123", "Pads", .95, (offer,))
    markup = part_detail_keyboard(0, candidate=candidate)

    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    urls = [
        button.url
        for row in markup.inline_keyboard
        for button in row
        if button.url
    ]
    assert "shop:add:0" in callbacks
    assert "https://shop.example/item/123" in urls


def test_shopping_list_keyboard_has_quantity_and_optimize_controls():
    item = ShoppingListItem(
        id=7,
        telegram_user_id=42,
        brand="ATE",
        article="123",
        title="Pads",
        quantity=2,
        vehicle_id=1,
    )
    markup = shopping_list_keyboard([item])
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert "shop:qty:7:-1" in callbacks
    assert "shop:qty:7:1" in callbacks
    assert "shop:optimize" in callbacks


def test_purchase_plan_keyboard_exposes_only_valid_offer_urls():
    request = PurchaseRequest("ATE", "123", "Pads")
    valid = Offer(
        "Partner",
        "ATE",
        "123",
        "Pads",
        Decimal("1000"),
        2,
        .95,
        url="https://shop.example/item/123",
    )
    invalid = Offer(
        "Unsafe",
        "ATE",
        "123",
        "Pads",
        Decimal("900"),
        2,
        .9,
        url="javascript:alert(1)",
    )
    plan = PurchasePlan(
        "optimized",
        "Plan",
        (
            PurchaseChoice(request, valid),
            PurchaseChoice(request, invalid),
        ),
        Decimal("1900"),
        Decimal("0"),
        Decimal("1900"),
        2,
        2,
    )
    markup = purchase_plan_keyboard(plan)
    urls = [
        button.url
        for row in markup.inline_keyboard
        for button in row
        if button.url
    ]
    assert urls == ["https://shop.example/item/123"]
