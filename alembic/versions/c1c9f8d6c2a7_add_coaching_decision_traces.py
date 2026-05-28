"""add_coaching_decision_traces

Revision ID: c1c9f8d6c2a7
Revises: f3b9c8d2a1e4
Create Date: 2026-05-28 11:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c1c9f8d6c2a7"
down_revision: Union[str, Sequence[str], None] = "f3b9c8d2a1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coaching_decision_traces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(length=30), nullable=True),
        sa.Column("input_event_id", sa.String(length=200), nullable=True),
        sa.Column("safety_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("rules_fired", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("plan_before_safety", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("plan_after_safety", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("llm_prompt_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("llm_response_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_coaching_decision_traces_id"), "coaching_decision_traces", ["id"], unique=False)
    op.create_index(op.f("ix_coaching_decision_traces_user_id"), "coaching_decision_traces", ["user_id"], unique=False)
    op.create_index(op.f("ix_coaching_decision_traces_input_event_id"), "coaching_decision_traces", ["input_event_id"], unique=False)
    op.create_index(op.f("ix_coaching_decision_traces_correlation_id"), "coaching_decision_traces", ["correlation_id"], unique=False)
    op.create_index(op.f("ix_coaching_decision_traces_created_at"), "coaching_decision_traces", ["created_at"], unique=False)
    op.create_index("idx_decision_trace_user_created", "coaching_decision_traces", ["user_id", "created_at"], unique=False)
    op.create_index("idx_decision_trace_user_event", "coaching_decision_traces", ["user_id", "input_event_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_decision_trace_user_event", table_name="coaching_decision_traces")
    op.drop_index("idx_decision_trace_user_created", table_name="coaching_decision_traces")
    op.drop_index(op.f("ix_coaching_decision_traces_created_at"), table_name="coaching_decision_traces")
    op.drop_index(op.f("ix_coaching_decision_traces_correlation_id"), table_name="coaching_decision_traces")
    op.drop_index(op.f("ix_coaching_decision_traces_input_event_id"), table_name="coaching_decision_traces")
    op.drop_index(op.f("ix_coaching_decision_traces_user_id"), table_name="coaching_decision_traces")
    op.drop_index(op.f("ix_coaching_decision_traces_id"), table_name="coaching_decision_traces")
    op.drop_table("coaching_decision_traces")

