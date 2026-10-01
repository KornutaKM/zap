import os
import subprocess
import sys
from pathlib import Path


def test_support_case_lifecycle_and_attention_dedup(tmp_path: Path):
    db_path = tmp_path / "cases.db"
    script = r"""
import asyncio
from decimal import Decimal

from app.db import (
    append_order_case_note,
    assign_order_case,
    get_customer_order,
    get_order_case,
    init_db,
    list_operator_order_cases,
    list_user_order_cases,
    resolve_order_case,
)
from app.domain import Offer
from app.orders import create_order_from_plan, revalidate_order
from app.procurement import PurchaseChoice, PurchasePlan, PurchaseRequest


class MissingSearch:
    async def parts(self, vehicle, query):
        return []


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
    order = await create_order_from_plan(
        42,
        build_plan(),
        vehicle_id=None,
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
    )

    first = await revalidate_order(
        42,
        order.id,
        vehicle=None,
        search_service=MissingSearch(),
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
    )
    assert first is not None
    assert first.order.status == "needs_attention"

    cases = await list_user_order_cases(42)
    assert len(cases) == 1
    case = cases[0]
    assert case.case_type == "availability"
    assert case.priority == "urgent"

    second = await revalidate_order(
        42,
        order.id,
        vehicle=None,
        search_service=MissingSearch(),
        shipping_fee=Decimal("500"),
        free_threshold=Decimal("999999"),
    )
    assert second is not None
    cases = await list_user_order_cases(42)
    assert len(cases) == 1
    assert cases[0].id == case.id

    assigned = await assign_order_case(case.id, 9001)
    assert assigned is not None
    assert assigned.status == "in_review"
    assert assigned.assigned_operator_user_id == 9001

    note = await append_order_case_note(
        case.id,
        author_user_id=9001,
        author_role="operator_internal",
        body="Связаться с поставщиком.",
    )
    assert note is not None

    operator_queue = await list_operator_order_cases()
    assert any(item.id == case.id for item in operator_queue)

    resolved = await resolve_order_case(
        case.id,
        9001,
        "Позиция недоступна; предложена замена.",
    )
    assert resolved is not None
    assert resolved.status == "resolved"
    assert resolved.resolution == "Позиция недоступна; предложена замена."

    loaded = await get_order_case(case.id)
    assert loaded is not None
    final_case, notes = loaded
    assert final_case.status == "resolved"
    assert any(item.author_role == "operator_internal" for item in notes)

    operator_queue = await list_operator_order_cases()
    assert not any(item.id == case.id for item in operator_queue)

    order_loaded = await get_customer_order(42, order.id)
    assert order_loaded is not None
    assert order_loaded[0].status == "needs_attention"


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
