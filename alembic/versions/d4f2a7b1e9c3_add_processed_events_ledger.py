"""add_processed_events_ledger

Revision ID: d4f2a7b1e9c3
Revises: c1c9f8d6c2a7
Create Date: 2026-05-28 11:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f2a7b1e9c3"
down_revision: Union[str, Sequence[str], None] = "c1c9f8d6c2a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(op.f("ix_processed_events_id"), "processed_events", ["id"], unique=False)
    op.create_index(op.f("ix_processed_events_event_id"), "processed_events", ["event_id"], unique=False)
    op.create_index(op.f("ix_processed_events_source"), "processed_events", ["source"], unique=False)
    op.create_index(op.f("ix_processed_events_user_id"), "processed_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_processed_events_created_at"), "processed_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_processed_events_created_at"), table_name="processed_events")
    op.drop_index(op.f("ix_processed_events_user_id"), table_name="processed_events")
    op.drop_index(op.f("ix_processed_events_source"), table_name="processed_events")
    op.drop_index(op.f("ix_processed_events_event_id"), table_name="processed_events")
    op.drop_index(op.f("ix_processed_events_id"), table_name="processed_events")
    op.drop_table("processed_events")

