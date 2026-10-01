import os
import subprocess
import sys
from pathlib import Path


def test_order_cancellation_stops_at_external_checkout_boundary(tmp_path: Path):
    db_path = tmp_path / "cancel.db"
    script = r"""
import asyncio
from decimal import Decimal

from app.checkout import CheckoutRegistry
from app.db import init_db
from app.domain import DeliveryProfile, Offer, PartCandidate
from app.orders import (
    cancel_local_order,
    checkout_ready_order,
    create_order_from_plan,
    revalidate_order,
)
from app.procurement import PurchaseChoice, PurchasePlan, PurchaseRequest


class FakeSearch:
    async def parts(self, vehicle, query):
        offer = Offer(
            "Store", "ATE", "123", "Pads",
            Decimal("1000"), 2, .9,
            url="https://shop.example/item/123",
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


def build_plan():
    request = PurchaseRequest("ATE", "123", "Pads", 1)
    offer = Offer(
        "Store", "ATE", "123", "Pads",
        Decimal("1000"), 2, .9,
        url="https://shop.example/item/123",
    )
    return PurchasePlan(
        "optimized", "Plan",
        (PurchaseChoice(request, offer),),
        Decimal("1000"), Decimal("500"), Decimal("1500"), 1, 2,
    )


async def main():
    await init_db()

    draft = await create_order_from_plan(
        42, build_plan(), vehicle_id=None,
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
    )
    cancelled = await cancel_local_order(42, draft.id)
    assert cancelled is not None
    assert cancelled.status == "cancelled"

    started = await create_order_from_plan(
        42, build_plan(), vehicle_id=None,
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
        delivery_profile=delivery_profile(),
    )
    checked = await revalidate_order(
        42, started.id,
        vehicle=None,
        search_service=FakeSearch(),
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
    )
    assert checked is not None and checked.order.status == "ready"

    checkout = await checkout_ready_order(42, started.id, CheckoutRegistry())
    assert checkout is not None
    assert checkout.status == "awaiting_manual_checkout"

    refused = await cancel_local_order(42, started.id)
    assert refused is not None
    assert refused.status == "awaiting_manual_checkout"


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
