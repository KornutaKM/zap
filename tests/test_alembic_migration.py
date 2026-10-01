import os
import subprocess
import sys
from pathlib import Path


def test_alembic_revision_is_applied_and_idempotent(tmp_path: Path):
    db_path = tmp_path / "alembic.db"
    script = r"""
import asyncio
import sqlite3
import sys

from app.db import init_db

db_path = sys.argv[1]

asyncio.run(init_db())
asyncio.run(init_db())

conn = sqlite3.connect(db_path)
revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
tables = {
    row[0]
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
}
conn.close()

assert revision == ("20261001_0004",), revision
assert "garage_vehicles" in tables
assert "saved_purchase_quotes" in tables
assert "price_history" in tables
assert "orders" in tables
assert "order_provider_groups" in tables
assert "order_lines" in tables
assert "order_events" in tables
assert "delivery_profiles" in tables
assert "order_cases" in tables
assert "order_case_notes" in tables
"""
    env = os.environ.copy()
    env.pop("BOT_TOKEN", None)
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    result = subprocess.run(
        [sys.executable, "-c", script, str(db_path)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
