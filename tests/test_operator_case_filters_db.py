import os
import subprocess
import sys
from pathlib import Path


def test_operator_case_filters_are_server_side(tmp_path: Path):
    db_path = tmp_path / "filters.db"
    script = r"""
import asyncio
from decimal import Decimal

from app.db import (
    assign_order_case,
    create_order_case,
    init_db,
    list_operator_order_cases,
)
from app.domain import Offer
from app.orders import create_order_from_plan
from app.procurement import PurchaseChoice, PurchasePlan, PurchaseRequest


def plan():
    req = PurchaseRequest("ATE", "123", "Pads", 1)
    offer = Offer("Store", "ATE", "123", "Pads", Decimal("100"), 1, .9)
    return PurchasePlan(
        "optimized",
        "Plan",
        (PurchaseChoice(req, offer),),
        Decimal("100"),
        Decimal("0"),
        Decimal("100"),
        1,
        1,
    )


async def main():
    await init_db()
    first_order = await create_order_from_plan(42, plan(), vehicle_id=None)
    second_order = await create_order_from_plan(43, plan(), vehicle_id=None)

    urgent = await create_order_case(
        42,
        first_order.id,
        case_type="support",
        summary="Urgent support",
        priority="urgent",
    )
    ret = await create_order_case(
        43,
        second_order.id,
        case_type="return",
        summary="Return",
        priority="normal",
    )
    assert urgent is not None and ret is not None
    await assign_order_case(ret.id, 9001)

    urgent_rows = await list_operator_order_cases(priority="urgent")
    assert [item.id for item in urgent_rows] == [urgent.id]

    return_rows = await list_operator_order_cases(case_type="return")
    assert [item.id for item in return_rows] == [ret.id]

    mine = await list_operator_order_cases(assigned_operator_user_id=9001)
    assert [item.id for item in mine] == [ret.id]

    unassigned = await list_operator_order_cases(only_unassigned=True)
    assert [item.id for item in unassigned] == [urgent.id]


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
