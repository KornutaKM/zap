"""add delivery profiles and order snapshots

Revision ID: 20261001_0003
Revises: 20261001_0002
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0003"
down_revision: Union[str, Sequence[str], None] = "20261001_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("address_line1", sa.String(250), nullable=False),
        sa.Column("address_line2", sa.String(250), nullable=True),
        sa.Column("postal_code", sa.String(40), nullable=True),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_delivery_profiles_telegram_user_id",
        "delivery_profiles",
        ["telegram_user_id"],
        unique=True,
    )

    op.add_column(
        "orders",
        sa.Column("delivery_profile_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("delivery_snapshot_json", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_orders_delivery_profile_id",
        "orders",
        ["delivery_profile_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_orders_delivery_profile_id", table_name="orders")
    op.drop_column("orders", "delivery_snapshot_json")
    op.drop_column("orders", "delivery_profile_id")
    op.drop_table("delivery_profiles")
