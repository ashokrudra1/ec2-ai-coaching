"""add_cost_and_usage_metering

Revision ID: e2a1c4b7f9d1
Revises: d4f2a7b1e9c3
Create Date: 2026-05-28 11:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2a1c4b7f9d1"
down_revision: Union[str, Sequence[str], None] = "d4f2a7b1e9c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("monthly_token_quota", sa.Integer(), nullable=True, server_default="500000"))
    op.add_column("users", sa.Column("monthly_tokens_used", sa.Integer(), nullable=True, server_default="0"))

    op.create_table(
        "ai_cost_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("org_id", sa.String(length=50), nullable=True),
        sa.Column("feature", sa.String(length=50), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=True),
        sa.Column("model", sa.String(length=50), nullable=True),
        sa.Column("tokens_estimated", sa.Integer(), nullable=True),
        sa.Column("cost_usd_estimated", sa.Float(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_cost_events_id"), "ai_cost_events", ["id"], unique=False)
    op.create_index(op.f("ix_ai_cost_events_user_id"), "ai_cost_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_ai_cost_events_org_id"), "ai_cost_events", ["org_id"], unique=False)
    op.create_index(op.f("ix_ai_cost_events_feature"), "ai_cost_events", ["feature"], unique=False)
    op.create_index(op.f("ix_ai_cost_events_model"), "ai_cost_events", ["model"], unique=False)
    op.create_index(op.f("ix_ai_cost_events_correlation_id"), "ai_cost_events", ["correlation_id"], unique=False)
    op.create_index(op.f("ix_ai_cost_events_created_at"), "ai_cost_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_cost_events_created_at"), table_name="ai_cost_events")
    op.drop_index(op.f("ix_ai_cost_events_correlation_id"), table_name="ai_cost_events")
    op.drop_index(op.f("ix_ai_cost_events_model"), table_name="ai_cost_events")
    op.drop_index(op.f("ix_ai_cost_events_feature"), table_name="ai_cost_events")
    op.drop_index(op.f("ix_ai_cost_events_org_id"), table_name="ai_cost_events")
    op.drop_index(op.f("ix_ai_cost_events_user_id"), table_name="ai_cost_events")
    op.drop_index(op.f("ix_ai_cost_events_id"), table_name="ai_cost_events")
    op.drop_table("ai_cost_events")

    op.drop_column("users", "monthly_tokens_used")
    op.drop_column("users", "monthly_token_quota")

