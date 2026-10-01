"""baseline current Zap schema

Revision ID: 20261001_0001
Revises:
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


metadata = sa.MetaData()

sa.Table(
    "vehicles",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, unique=True, index=True),
    sa.Column("brand", sa.String(80), nullable=False),
    sa.Column("model", sa.String(120), nullable=False),
    sa.Column("year", sa.Integer(), nullable=False),
    sa.Column("vin", sa.String(17), nullable=True),
)

sa.Table(
    "search_history",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, index=True),
    sa.Column("query", sa.String(250), nullable=False),
    sa.Column("vehicle_label", sa.String(250), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

sa.Table(
    "favorite_parts",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, index=True),
    sa.Column("brand", sa.String(120), nullable=False),
    sa.Column("article", sa.String(120), nullable=False),
    sa.Column("title", sa.String(250), nullable=False),
)

sa.Table(
    "price_alerts",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, index=True),
    sa.Column("vehicle_id", sa.Integer(), nullable=True, index=True),
    sa.Column("brand", sa.String(120), nullable=False),
    sa.Column("article", sa.String(120), nullable=False, index=True),
    sa.Column("title", sa.String(250), nullable=False),
    sa.Column("target_price", sa.Numeric(12, 2), nullable=False),
    sa.Column("last_price", sa.Numeric(12, 2), nullable=True),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
)

sa.Table(
    "shopping_list",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, index=True),
    sa.Column("vehicle_id", sa.Integer(), nullable=True, index=True),
    sa.Column("brand", sa.String(120), nullable=False),
    sa.Column("article", sa.String(120), nullable=False, index=True),
    sa.Column("title", sa.String(250), nullable=False),
    sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

sa.Table(
    "saved_purchase_quotes",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, index=True),
    sa.Column("vehicle_id", sa.Integer(), nullable=True, index=True),
    sa.Column("title", sa.String(250), nullable=False),
    sa.Column("grand_total", sa.Numeric(12, 2), nullable=False),
    sa.Column("provider_count", sa.Integer(), nullable=False),
    sa.Column("max_delivery_days", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(40), nullable=False, server_default="saved", index=True),
    sa.Column("snapshot_json", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

sa.Table(
    "price_history",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("provider", sa.String(120), nullable=False, index=True),
    sa.Column("brand", sa.String(120), nullable=False, index=True),
    sa.Column("article", sa.String(120), nullable=False, index=True),
    sa.Column("price", sa.Numeric(12, 2), nullable=False),
    sa.Column("delivery_days", sa.Integer(), nullable=False),
    sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
)

sa.Table(
    "garage_vehicles",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, index=True),
    sa.Column("brand", sa.String(80), nullable=False),
    sa.Column("model", sa.String(120), nullable=False),
    sa.Column("year", sa.Integer(), nullable=False),
    sa.Column("vin", sa.String(17), nullable=True),
    sa.Column("generation_code", sa.String(40), nullable=True),
    sa.Column("engine", sa.String(80), nullable=True),
    sa.Column("fuel", sa.String(40), nullable=True),
    sa.Column("drive", sa.String(40), nullable=True),
    sa.Column("power_hp", sa.Integer(), nullable=True),
    sa.Column("modification_key", sa.String(120), nullable=True),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false(), index=True),
)


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

    # Frozen baseline: safe for both new databases and schemas previously
    # bootstrapped via SQLAlchemy create_all.
    for table in metadata.sorted_tables:
        table.create(bind=bind, checkfirst=True)

    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("garage_vehicles")}
    for name, column in GARAGE_COLUMNS.items():
        if name not in existing:
            op.add_column("garage_vehicles", column)

    # Legacy hand-created garage tables may not have ORM indexes.
    inspector = sa.inspect(bind)
    index_names = {item["name"] for item in inspector.get_indexes("garage_vehicles")}
    if "ix_garage_vehicles_telegram_user_id" not in index_names:
        op.create_index(
            "ix_garage_vehicles_telegram_user_id",
            "garage_vehicles",
            ["telegram_user_id"],
        )
    if "ix_garage_vehicles_is_active" not in index_names:
        op.create_index(
            "ix_garage_vehicles_is_active",
            "garage_vehicles",
            ["is_active"],
        )


def downgrade() -> None:
    # Baseline downgrade is intentionally non-destructive.
    pass
