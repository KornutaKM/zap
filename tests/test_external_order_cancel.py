import os
import subprocess
import sys
from pathlib import Path


def test_external_order_cancellation_uses_provider_adapter(tmp_path: Path):
    db_path = tmp_path / "external-cancel.db"
    script = r"""
import asyncio
from decimal import Decimal

from app.checkout import CheckoutRegistry, CheckoutResult
from app.db import (
    get_customer_order,
    init_db,
    update_order_status,
    update_supplier_group_checkout,
)
from app.domain import DeliveryProfile, Offer, PartCandidate
from app.orders import (
    create_order_from_plan,
    request_external_order_cancellation,
    revalidate_order,
)
from app.procurement import PurchaseChoice, PurchasePlan, PurchaseRequest


class FakeSearch:
    async def parts(self, vehicle, query):
        offer = Offer(
            "API Store", "ATE", "123", "Pads",
            Decimal("1000"), 2, .9,
            url="https://shop.example/item/123",
        )
        return [PartCandidate("ATE", "123", "Pads", .9, (offer,))]


class CancelAdapter:
    provider_name = "API Store"

    async def create_checkout(self, request):
        raise AssertionError("not used")

    async def get_status(self, external_order_id):
        return CheckoutResult(
            status="placed",
            mode="api",
            external_order_id=external_order_id,
        )

    async def cancel_checkout(self, external_order_id):
        return CheckoutResult(
            status="cancelled",
            mode="api",
            external_order_id=external_order_id,
        )


def profile():
    return DeliveryProfile(
        id=1,
        telegram_user_id=42,
        full_name="Иван Иванов",
        phone="+79991234567",
        email="ivan@example.com",
        country="Россия",
        city="Москва",
        address_line1="ул. Примерная, 1",
    )


async def main():
    await init_db()
    request = PurchaseRequest("ATE", "123", "Pads", 1)
    offer = Offer(
        "API Store", "ATE", "123", "Pads",
        Decimal("1000"), 2, .9,
        url="https://shop.example/item/123",
    )
    plan = PurchasePlan(
        "optimized", "Plan",
        (PurchaseChoice(request, offer),),
        Decimal("1000"), Decimal("500"), Decimal("1500"), 1, 2,
    )
    order = await create_order_from_plan(
        42, plan, vehicle_id=None,
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
        delivery_profile=profile(),
    )
    checked = await revalidate_order(
        42, order.id,
        vehicle=None,
        search_service=FakeSearch(),
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
    )
    assert checked is not None and checked.order.status == "ready"

    loaded = await get_customer_order(42, order.id)
    assert loaded is not None
    _, groups, _, _ = loaded
    group = groups[0]

    await update_supplier_group_checkout(
        order.id,
        group.id,
        status="placed",
        checkout_mode="api",
        external_order_id="ext-123",
        checkout_url=None,
        last_error=None,
    )
    await update_order_status(
        42,
        order.id,
        "placed",
        message="Placed",
    )

    cancelled = await request_external_order_cancellation(
        42,
        order.id,
        CheckoutRegistry([CancelAdapter()]),
    )
    assert cancelled is not None
    assert cancelled.status == "cancelled"

    loaded = await get_customer_order(42, order.id)
    assert loaded is not None
    final_order, final_groups, _, _ = loaded
    assert final_order.status == "cancelled"
    assert final_groups[0].status == "cancelled"


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
