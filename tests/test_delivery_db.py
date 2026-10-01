import os
import subprocess
import sys
from pathlib import Path


def test_delivery_profile_snapshot_is_explicit_and_immutable(tmp_path: Path):
    db_path = tmp_path / "delivery.db"
    script = r"""
import asyncio
from decimal import Decimal

from app.db import (
    get_customer_order,
    get_delivery_profile,
    init_db,
    save_delivery_profile,
)
from app.domain import Offer
from app.orders import apply_delivery_profile_to_order, create_order_from_plan
from app.procurement import PurchaseChoice, PurchasePlan, PurchaseRequest


def build_plan():
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
    return PurchasePlan(
        "optimized",
        "Plan",
        (PurchaseChoice(request, offer),),
        Decimal("1000"),
        Decimal("500"),
        Decimal("1500"),
        1,
        2,
    )


async def main():
    await init_db()

    first = await save_delivery_profile(
        42,
        full_name="Иван Иванов",
        phone="+79991234567",
        email="ivan@example.com",
        country="Россия",
        city="Москва",
        address_line1="Старый адрес, 1",
        postal_code="101000",
    )

    order = await create_order_from_plan(
        42,
        build_plan(),
        vehicle_id=None,
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
        delivery_profile=first,
    )

    loaded = await get_customer_order(42, order.id)
    assert loaded is not None
    saved_order = loaded[0]
    assert saved_order.delivery_snapshot is not None
    assert saved_order.delivery_snapshot["address_line1"] == "Старый адрес, 1"

    second = await save_delivery_profile(
        42,
        full_name="Иван Иванов",
        phone="+79991234567",
        email="ivan@example.com",
        country="Россия",
        city="Москва",
        address_line1="Новый адрес, 2",
        postal_code="101000",
    )
    current = await get_delivery_profile(42)
    assert current is not None
    assert current.address_line1 == "Новый адрес, 2"

    loaded = await get_customer_order(42, order.id)
    assert loaded is not None
    unchanged = loaded[0]
    assert unchanged.delivery_snapshot["address_line1"] == "Старый адрес, 1"

    updated = await apply_delivery_profile_to_order(42, order.id, second)
    assert updated is not None
    assert updated.delivery_snapshot is not None
    assert updated.delivery_snapshot["address_line1"] == "Новый адрес, 2"


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
