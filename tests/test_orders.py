import asyncio
from decimal import Decimal

import pytest

from app.domain import Offer, PartCandidate
from app.orders import create_order_from_plan
from app.procurement import PurchaseChoice, PurchasePlan, PurchaseRequest


def test_create_order_service_is_importable():
    assert callable(create_order_from_plan)


def test_valid_order_plan_math():
    request = PurchaseRequest("ATE", "123", "Pads", 2)
    offer = Offer("Store", "ATE", "123", "Pads", Decimal("1000"), 2, .9)
    plan = PurchasePlan(
        "optimized",
        "Plan",
        (PurchaseChoice(request, offer),),
        Decimal("2000"),
        Decimal("500"),
        Decimal("2500"),
        1,
        2,
    )
    assert plan.choices[0].subtotal == Decimal("2000")
