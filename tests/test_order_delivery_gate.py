import os
import subprocess
import sys
from pathlib import Path


def test_delivery_gate_transitions_needs_delivery_to_ready(tmp_path: Path):
    db_path = tmp_path / "delivery-gate.db"
    script = r"""
import asyncio
from decimal import Decimal

from app.db import init_db, save_delivery_profile
from app.domain import Offer, PartCandidate
from app.orders import (
    apply_delivery_profile_to_order,
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


async def main():
    await init_db()
    request = PurchaseRequest("ATE", "123", "Pads", 1)
    offer = Offer(
        "Store", "ATE", "123", "Pads",
        Decimal("1000"), 2, .9,
        url="https://shop.example/item/123",
    )
    plan = PurchasePlan(
        "optimized", "Plan",
        (PurchaseChoice(request, offer),),
        Decimal("1000"), Decimal("500"), Decimal("1500"), 1, 2,
    )

    order = await create_order_from_plan(
        42,
        plan,
        vehicle_id=None,
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
    )
    checked = await revalidate_order(
        42,
        order.id,
        vehicle=None,
        search_service=FakeSearch(),
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
    )
    assert checked is not None
    assert checked.order.status == "needs_delivery"

    profile = await save_delivery_profile(
        42,
        full_name="Иван Иванов",
        phone="+79991234567",
        email="ivan@example.com",
        country="Россия",
        city="Москва",
        address_line1="ул. Примерная, 1",
    )
    updated = await apply_delivery_profile_to_order(42, order.id, profile)
    assert updated is not None
    assert updated.status == "ready"
    assert updated.delivery_snapshot is not None
    assert updated.delivery_snapshot["city"] == "Москва"


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
