from decimal import Decimal

from app.domain import CustomerOrder, SupplierOrderGroup
from app.ui import order_detail_keyboard, orders_keyboard


def order(status: str, *, with_delivery: bool = True) -> CustomerOrder:
    return CustomerOrder(
        id=7,
        telegram_user_id=42,
        status=status,
        item_total=Decimal("1000"),
        shipping_total=Decimal("500"),
        grand_total=Decimal("1500"),
        provider_count=1,
        delivery_snapshot=(
            {
                "full_name": "Иван Иванов",
                "phone": "+79991234567",
                "email": "ivan@example.com",
                "country": "Россия",
                "city": "Москва",
                "address_line1": "ул. Примерная, 1",
                "address_line2": None,
                "postal_code": "101000",
                "comment": None,
            }
            if with_delivery
            else None
        ),
    )


def callbacks(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def urls(markup):
    return [
        button.url
        for row in markup.inline_keyboard
        for button in row
        if button.url
    ]


def test_ready_order_has_explicit_checkout_action():
    values = callbacks(order_detail_keyboard(order("ready"), []))
    assert "order:checkout:7" in values
    assert "order:revalidate:7" not in values


def test_draft_order_requires_revalidation():
    values = callbacks(order_detail_keyboard(order("draft"), []))
    assert "order:revalidate:7" in values
    assert "order:checkout:7" not in values


def test_manual_group_exposes_safe_deeplink_and_confirmation():
    group = SupplierOrderGroup(
        id=3,
        order_id=7,
        provider="Store",
        status="manual_required",
        item_total=Decimal("1000"),
        shipping_total=Decimal("500"),
        grand_total=Decimal("1500"),
        checkout_mode="deeplink",
        checkout_url="https://shop.example/checkout",
    )
    markup = order_detail_keyboard(order("awaiting_manual_checkout"), [group])
    assert "https://shop.example/checkout" in urls(markup)
    assert "order:manual:7:3" in callbacks(markup)


def test_order_list_opens_order_id():
    markup = orders_keyboard([order("draft")])
    assert "order:open:7" in callbacks(markup)



def test_draft_order_has_cancel_action():
    values = callbacks(order_detail_keyboard(order("draft"), []))
    assert "order:cancel:7" in values


def test_started_checkout_does_not_show_local_cancel():
    values = callbacks(order_detail_keyboard(order("awaiting_manual_checkout"), []))
    assert "order:cancel:7" not in values



def test_ready_order_without_delivery_blocks_checkout_button():
    values = callbacks(
        order_detail_keyboard(order("ready", with_delivery=False), [])
    )
    assert "order:checkout:7" not in values
    assert "order:delivery:7" in values
