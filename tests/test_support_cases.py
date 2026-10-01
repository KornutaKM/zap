import pytest
from decimal import Decimal

from app.domain import CustomerOrder
from app.support_cases import can_request_return, normalize_case_message


def order(status: str) -> CustomerOrder:
    return CustomerOrder(
        id=1,
        telegram_user_id=42,
        status=status,
        item_total=Decimal("100"),
        shipping_total=Decimal("0"),
        grand_total=Decimal("100"),
        provider_count=1,
    )


def test_return_is_limited_to_purchased_orders():
    assert can_request_return(order("placed"))
    assert can_request_return(order("completed"))
    assert not can_request_return(order("draft"))
    assert not can_request_return(order("cancelled"))


def test_case_message_is_normalized():
    assert normalize_case_message("  Нужна   помощь с заказом  ") == (
        "Нужна помощь с заказом"
    )
    with pytest.raises(ValueError):
        normalize_case_message("нет")
