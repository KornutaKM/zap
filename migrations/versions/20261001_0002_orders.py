"""add customer order aggregate

Revision ID: 20261001_0002
Revises: 20261001_0001
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0002"
down_revision: Union[str, Sequence[str], None] = "20261001_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
        sa.Column("source_quote_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("item_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("grand_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("provider_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_orders_telegram_user_id", "orders", ["telegram_user_id"])
    op.create_index("ix_orders_vehicle_id", "orders", ["vehicle_id"])
    op.create_index("ix_orders_source_quote_id", "orders", ["source_quote_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_provider_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("item_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("grand_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("checkout_mode", sa.String(40), nullable=False, server_default="deeplink"),
        sa.Column("external_order_id", sa.String(160), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_order_provider_groups_order_id", "order_provider_groups", ["order_id"])
    op.create_index("ix_order_provider_groups_provider", "order_provider_groups", ["provider"])
    op.create_index("ix_order_provider_groups_status", "order_provider_groups", ["status"])
    op.create_index("ix_order_provider_groups_external_order_id", "order_provider_groups", ["external_order_id"])

    op.create_table(
        "order_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("order_provider_groups.id"), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("brand", sa.String(120), nullable=False),
        sa.Column("article", sa.String(120), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("delivery_days", sa.Integer(), nullable=False),
        sa.Column("offer_url", sa.Text(), nullable=True),
        sa.Column("in_stock", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("price_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_order_lines_order_id", "order_lines", ["order_id"])
    op.create_index("ix_order_lines_group_id", "order_lines", ["group_id"])
    op.create_index("ix_order_lines_provider", "order_lines", ["provider"])
    op.create_index("ix_order_lines_brand", "order_lines", ["brand"])
    op.create_index("ix_order_lines_article", "order_lines", ["article"])

    op.create_table(
        "order_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("from_status", sa.String(40), nullable=True),
        sa.Column("to_status", sa.String(40), nullable=True),
        sa.Column("provider", sa.String(120), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"])
    op.create_index("ix_order_events_event_type", "order_events", ["event_type"])
    op.create_index("ix_order_events_created_at", "order_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("order_events")
    op.drop_table("order_lines")
    op.drop_table("order_provider_groups")
    op.drop_table("orders")
