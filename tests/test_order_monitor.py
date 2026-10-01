import asyncio

from app.checkout import CheckoutRegistry
from app.order_monitor import refresh_active_order_statuses


def test_order_monitor_service_is_importable():
    assert callable(refresh_active_order_statuses)
    assert isinstance(CheckoutRegistry(), CheckoutRegistry)
