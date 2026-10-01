"""baseline current Zap schema

Revision ID: 20261001_0001
Revises:
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import Base


revision: str = "20261001_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


GARAGE_COLUMNS = {
    "generation_code": sa.Column("generation_code", sa.String(length=40), nullable=True),
    "engine": sa.Column("engine", sa.String(length=80), nullable=True),
    "fuel": sa.Column("fuel", sa.String(length=40), nullable=True),
    "drive": sa.Column("drive", sa.String(length=40), nullable=True),
    "power_hp": sa.Column("power_hp", sa.Integer(), nullable=True),
    "modification_key": sa.Column("modification_key", sa.String(length=120), nullable=True),
}


def upgrade() -> None:
    bind = op.get_bind()

    # Idempotent baseline: safe for databases previously created via create_all.
    Base.metadata.create_all(bind=bind)

    inspector = sa.inspect(bind)
    if "garage_vehicles" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("garage_vehicles")}
    for name, column in GARAGE_COLUMNS.items():
        if name not in existing:
            op.add_column("garage_vehicles", column)


def downgrade() -> None:
    # Baseline downgrade is intentionally non-destructive.
    pass
