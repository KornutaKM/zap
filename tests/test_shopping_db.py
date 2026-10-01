import os
import subprocess
import sys
from pathlib import Path


def test_shopping_list_persists_and_updates_quantity(tmp_path: Path):
    db_path = tmp_path / "shopping.db"
    script = r"""
import asyncio
import sys

db_path = sys.argv[1]

from app.db import (
    add_shopping_item,
    change_shopping_quantity,
    init_db,
    list_shopping_items,
    remove_shopping_item,
)


async def main():
    await init_db()

    first = await add_shopping_item(
        42,
        vehicle_id=1,
        brand="ATE",
        article="123",
        title="Pads",
        quantity=1,
    )
    second = await add_shopping_item(
        42,
        vehicle_id=1,
        brand="ATE",
        article="123",
        title="Pads",
        quantity=2,
    )
    assert first.id == second.id
    assert second.quantity == 3

    changed = await change_shopping_quantity(42, second.id, -1)
    assert changed is not None
    assert changed.quantity == 2

    items = await list_shopping_items(42)
    assert len(items) == 1
    assert items[0].quantity == 2

    assert await remove_shopping_item(42, second.id)
    assert await list_shopping_items(42) == []


asyncio.run(main())
"""
    env = os.environ.copy()
    env["BOT_TOKEN"] = "test-token"
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    result = subprocess.run(
        [sys.executable, "-c", script, str(db_path)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
