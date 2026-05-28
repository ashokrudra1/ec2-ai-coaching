"""add_elite_coaching_monitoring

Revision ID: f3b9c8d2a1e4
Revises: b8daa1c0dbf5
Create Date: 2026-05-28 09:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f3b9c8d2a1e4"
down_revision: Union[str, Sequence[str], None] = "b8daa1c0dbf5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ctl_time_constant_days", sa.Float(), nullable=True, server_default="42.0"))
    op.add_column("users", sa.Column("atl_time_constant_days", sa.Float(), nullable=True, server_default="7.0"))
    op.add_column("users", sa.Column("fitness_state_updated_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("last_training_stress_date", sa.DateTime(), nullable=True))

    op.add_column("activities", sa.Column("prescribed_workout", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")))
    op.add_column("activities", sa.Column("compliance_score", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("pace_compliance_score", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("hr_compliance_score", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("compliance_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")))

    op.create_table(
        "safety_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("alert_type", sa.String(length=50), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("source_metric", sa.String(length=50), nullable=True),
        sa.Column("source_value", sa.Float(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_safety_alerts_id"), "safety_alerts", ["id"], unique=False)
    op.create_index(op.f("ix_safety_alerts_user_id"), "safety_alerts", ["user_id"], unique=False)
    op.create_index(op.f("ix_safety_alerts_alert_type"), "safety_alerts", ["alert_type"], unique=False)
    op.create_index(op.f("ix_safety_alerts_is_resolved"), "safety_alerts", ["is_resolved"], unique=False)
    op.create_index(op.f("ix_safety_alerts_created_at"), "safety_alerts", ["created_at"], unique=False)
    op.create_index("idx_safety_alert_user_open", "safety_alerts", ["user_id", "is_resolved"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_safety_alert_user_open", table_name="safety_alerts")
    op.drop_index(op.f("ix_safety_alerts_created_at"), table_name="safety_alerts")
    op.drop_index(op.f("ix_safety_alerts_is_resolved"), table_name="safety_alerts")
    op.drop_index(op.f("ix_safety_alerts_alert_type"), table_name="safety_alerts")
    op.drop_index(op.f("ix_safety_alerts_user_id"), table_name="safety_alerts")
    op.drop_index(op.f("ix_safety_alerts_id"), table_name="safety_alerts")
    op.drop_table("safety_alerts")

    op.drop_column("activities", "compliance_breakdown")
    op.drop_column("activities", "hr_compliance_score")
    op.drop_column("activities", "pace_compliance_score")
    op.drop_column("activities", "compliance_score")
    op.drop_column("activities", "prescribed_workout")

    op.drop_column("users", "last_training_stress_date")
    op.drop_column("users", "fitness_state_updated_at")
    op.drop_column("users", "atl_time_constant_days")
    op.drop_column("users", "ctl_time_constant_days")
