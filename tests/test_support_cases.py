from datetime import datetime, timedelta, timezone
import pytest
from decimal import Decimal

from app.domain import CustomerOrder
from app.support_cases import can_request_return, case_is_overdue, normalize_case_message, operator_queue_stats


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



def test_operator_sla_and_queue_stats():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    urgent = __import__("app.domain", fromlist=["OrderCase"]).OrderCase(
        id=1,
        order_id=10,
        telegram_user_id=42,
        case_type="availability",
        status="open",
        priority="urgent",
        summary="Missing",
        created_at=(now - timedelta(hours=5)).isoformat(),
    )
    normal = __import__("app.domain", fromlist=["OrderCase"]).OrderCase(
        id=2,
        order_id=11,
        telegram_user_id=43,
        case_type="return",
        status="in_review",
        priority="normal",
        summary="Return",
        assigned_operator_user_id=9001,
        created_at=(now - timedelta(hours=2)).isoformat(),
    )

    assert case_is_overdue(urgent, urgent_hours=4, normal_hours=24, now=now)
    assert not case_is_overdue(normal, urgent_hours=4, normal_hours=24, now=now)

    stats = operator_queue_stats(
        [urgent, normal],
        urgent_hours=4,
        normal_hours=24,
        now=now,
    )
    assert stats.total == 2
    assert stats.urgent == 1
    assert stats.overdue == 1
    assert stats.unassigned == 1
    assert stats.returns == 1
