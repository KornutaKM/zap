import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import settings


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    database_url = settings().database_url.replace("%", "%%")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _upgrade_sync() -> None:
    command.upgrade(_alembic_config(), "head")


async def upgrade_database() -> None:
    await asyncio.to_thread(_upgrade_sync)
