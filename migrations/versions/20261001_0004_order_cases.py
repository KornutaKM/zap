"""add order support cases

Revision ID: 20261001_0004
Revises: 20261001_0003
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0004"
down_revision: Union[str, Sequence[str], None] = "20261001_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("orders.id"),
            nullable=False,
        ),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("case_type", sa.String(40), nullable=False),
        sa.Column(
            "status",
            sa.String(40),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="normal",
        ),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column(
            "assigned_operator_user_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column("resolution", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_order_cases_order_id", "order_cases", ["order_id"])
    op.create_index(
        "ix_order_cases_telegram_user_id",
        "order_cases",
        ["telegram_user_id"],
    )
    op.create_index("ix_order_cases_case_type", "order_cases", ["case_type"])
    op.create_index("ix_order_cases_status", "order_cases", ["status"])
    op.create_index("ix_order_cases_priority", "order_cases", ["priority"])
    op.create_index(
        "ix_order_cases_assigned_operator_user_id",
        "order_cases",
        ["assigned_operator_user_id"],
    )
    op.create_index(
        "ix_order_cases_created_at",
        "order_cases",
        ["created_at"],
    )

    op.create_table(
        "order_case_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("order_cases.id"),
            nullable=False,
        ),
        sa.Column("author_user_id", sa.BigInteger(), nullable=True),
        sa.Column("author_role", sa.String(20), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_order_case_notes_case_id",
        "order_case_notes",
        ["case_id"],
    )
    op.create_index(
        "ix_order_case_notes_created_at",
        "order_case_notes",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("order_case_notes")
    op.drop_table("order_cases")
