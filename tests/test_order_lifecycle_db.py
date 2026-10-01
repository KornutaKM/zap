import os
import subprocess
import sys
from pathlib import Path


def test_order_lifecycle_with_deeplink_checkout(tmp_path: Path):
    db_path = tmp_path / "orders.db"
    script = r"""
import asyncio
from decimal import Decimal

from app.checkout import CheckoutRegistry
from app.db import get_customer_order, init_db
from app.domain import DeliveryProfile, Offer, PartCandidate
from app.orders import (
    checkout_ready_order,
    create_order_from_plan,
    mark_manual_group_placed,
    revalidate_order,
)
from app.procurement import PurchaseChoice, PurchasePlan, PurchaseRequest


class FakeSearch:
    async def parts(self, vehicle, query):
        offer = Offer(
            provider="Store",
            brand="ATE",
            article="123",
            title="Pads",
            price=Decimal("1000"),
            delivery_days=2,
            quality=.9,
            url="https://shop.example/item/123",
            in_stock=True,
        )
        return [PartCandidate("ATE", "123", "Pads", .9, (offer,))]


def delivery_profile():
    return DeliveryProfile(
        id=1,
        telegram_user_id=42,
        full_name="Иван Иванов",
        phone="+79991234567",
        email="ivan@example.com",
        country="Россия",
        city="Москва",
        address_line1="ул. Примерная, 1",
        postal_code="101000",
    )


async def main():
    await init_db()

    request = PurchaseRequest("ATE", "123", "Pads", 1)
    offer = Offer(
        "Store",
        "ATE",
        "123",
        "Pads",
        Decimal("1000"),
        2,
        .9,
        url="https://shop.example/item/123",
    )
    plan = PurchasePlan(
        mode="optimized",
        title="Plan",
        choices=(PurchaseChoice(request, offer),),
        item_total=Decimal("1000"),
        shipping_total=Decimal("500"),
        grand_total=Decimal("1500"),
        provider_count=1,
        max_delivery_days=2,
    )

    order = await create_order_from_plan(
        42,
        plan,
        vehicle_id=None,
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
        delivery_profile=delivery_profile(),
    )
    assert order.status == "draft"

    checked = await revalidate_order(
        42,
        order.id,
        vehicle=None,
        search_service=FakeSearch(),
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
    )
    assert checked is not None
    assert checked.order.status == "ready"

    checkout = await checkout_ready_order(42, order.id, CheckoutRegistry())
    assert checkout is not None
    assert checkout.status == "awaiting_manual_checkout"

    loaded = await get_customer_order(42, order.id)
    assert loaded is not None
    _, groups, lines, events = loaded
    assert len(groups) == 1
    assert groups[0].status == "manual_required"
    assert lines[0].price_confirmed
    assert groups[0].checkout_url == "https://shop.example/item/123"

    placed = await mark_manual_group_placed(42, order.id, groups[0].id)
    assert placed is not None
    assert placed.status == "placed"

    loaded = await get_customer_order(42, order.id)
    assert loaded is not None
    final_order, final_groups, _, final_events = loaded
    assert final_order.status == "placed"
    assert final_groups[0].status == "placed"
    assert len(final_events) >= 4


asyncio.run(main())
"""
    env = os.environ.copy()
    env.pop("BOT_TOKEN", None)
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
