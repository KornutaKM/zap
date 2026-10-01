import os
import subprocess
import sys
from pathlib import Path


def test_saved_quote_and_price_history_persist(tmp_path: Path):
    db_path = tmp_path / "quotes.db"
    script = r"""
import asyncio
import sys
from decimal import Decimal

from app.db import (
    delete_purchase_quote,
    get_purchase_quote,
    init_db,
    list_price_history,
    list_purchase_quotes,
    record_price_observations,
    save_purchase_quote,
)
from app.domain import Offer


async def main():
    await init_db()

    snapshot = {
        "mode": "optimized",
        "title": "Оптимальный заказ",
        "item_total": "1000",
        "shipping_total": "500",
        "grand_total": "1500",
        "provider_count": 1,
        "max_delivery_days": 2,
        "choices": [],
    }
    quote = await save_purchase_quote(
        42,
        vehicle_id=1,
        title="Оптимальный заказ",
        grand_total=Decimal("1500"),
        provider_count=1,
        max_delivery_days=2,
        snapshot=snapshot,
    )
    assert quote.grand_total == Decimal("1500")
    assert len(await list_purchase_quotes(42)) == 1

    loaded = await get_purchase_quote(42, quote.id)
    assert loaded is not None
    _, payload = loaded
    assert payload["grand_total"] == "1500"

    offers = [
        Offer("Store", "ATE", "123", "Pads", Decimal("1200"), 2, .9),
        Offer("Store", "ATE", "123", "Pads", Decimal("1100"), 2, .9),
    ]
    assert await record_price_observations(offers) == 2
    points = await list_price_history("ATE", "123")
    assert len(points) == 2
    assert points[0].price == Decimal("1100")

    assert await delete_purchase_quote(42, quote.id)
    assert await list_purchase_quotes(42) == []


asyncio.run(main())
"""
    env = os.environ.copy()
    env["BOT_TOKEN"] = "test-token"
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
