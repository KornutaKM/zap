import asyncio
from dataclasses import dataclass
from html import escape
from typing import Awaitable, Callable

from app.checkout import CheckoutRegistry
from app.db import get_customer_order, list_orders_for_status_monitor
from app.domain import CustomerOrder
from app.orders import refresh_order_checkout_status
from app.ui import order_status_label


@dataclass(frozen=True, slots=True)
class OrderStatusChange:
    order_id: int
    telegram_user_id: int
    old_status: str
    new_status: str


async def refresh_active_order_statuses(
    registry: CheckoutRegistry,
) -> list[OrderStatusChange]:
    changes: list[OrderStatusChange] = []
    orders = await list_orders_for_status_monitor()

    for order in orders:
        loaded = await get_customer_order(order.telegram_user_id, order.id)
        if loaded is None:
            continue
        _, groups, _, _ = loaded
        if not any(group.external_order_id for group in groups):
            continue

        updated = await refresh_order_checkout_status(
            order.telegram_user_id,
            order.id,
            registry,
        )
        if updated is None or updated.status == order.status:
            continue

        changes.append(
            OrderStatusChange(
                order_id=order.id,
                telegram_user_id=order.telegram_user_id,
                old_status=order.status,
                new_status=updated.status,
            )
        )

    return changes


async def order_status_loop(
    bot,
    registry: CheckoutRegistry,
    interval_seconds: int,
) -> None:
    interval = max(60, interval_seconds)

    while True:
        await asyncio.sleep(interval)
        changes = await refresh_active_order_statuses(registry)
        for change in changes:
            try:
                await bot.send_message(
                    change.telegram_user_id,
                    f"<b>Заказ #{change.order_id}</b>\n"
                    f"Статус изменился: "
                    f"{escape(order_status_label(change.old_status))} → "
                    f"<b>{escape(order_status_label(change.new_status))}</b>",
                )
            except Exception:
                # Delivery errors must not stop provider status monitoring.
                continue
