import os
import subprocess
import sys
from pathlib import Path


def test_legacy_garage_schema_is_migrated(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    script = r"""
import asyncio
import sqlite3
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
conn.execute(
    '''
    CREATE TABLE garage_vehicles (
        id INTEGER PRIMARY KEY,
        telegram_user_id BIGINT NOT NULL,
        brand VARCHAR(80) NOT NULL,
        model VARCHAR(120) NOT NULL,
        year INTEGER NOT NULL,
        vin VARCHAR(17),
        is_active BOOLEAN NOT NULL
    )
    '''
)
conn.execute(
    '''
    INSERT INTO garage_vehicles
    (id, telegram_user_id, brand, model, year, vin, is_active)
    VALUES (1, 42, 'BMW', 'X3 G01', 2020, NULL, 1)
    '''
)
conn.commit()
conn.close()

from app.db import init_db
asyncio.run(init_db())

conn = sqlite3.connect(db_path)
columns = {row[1] for row in conn.execute('PRAGMA table_info(garage_vehicles)')}
row = conn.execute(
    'SELECT brand, model, year FROM garage_vehicles WHERE id = 1'
).fetchone()
conn.close()

required = {
    'generation_code',
    'engine',
    'fuel',
    'drive',
    'power_hp',
    'modification_key',
}
assert required.issubset(columns), columns
assert row == ('BMW', 'X3 G01', 2020), row
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
