"""add_strava_byok_fields

Revision ID: a42c7e9b31d0
Revises: f3b9c8d2a1e4
Create Date: 2026-05-28 10:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a42c7e9b31d0"
down_revision: Union[str, Sequence[str], None] = "f3b9c8d2a1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("strava_custom_client_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("strava_custom_client_secret_encrypted", sa.String(), nullable=True))
    op.add_column("users", sa.Column("is_using_byok", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(
        "ix_users_strava_custom_client_id",
        "users",
        ["strava_custom_client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_users_strava_custom_client_id", table_name="users")
    op.drop_column("users", "is_using_byok")
    op.drop_column("users", "strava_custom_client_secret_encrypted")
    op.drop_column("users", "strava_custom_client_id")
