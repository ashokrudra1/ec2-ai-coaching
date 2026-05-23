"""sync schema

Revision ID: ef92a24450f5
Revises: 
Create Date: 2026-05-04 16:59:37.040826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef92a24450f5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at columns
    op.add_column('activities', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('activity_analytics', sa.Column('created_at', sa.DateTime(), nullable=True))

    # Indexes
    op.create_index(op.f('ix_activities_user_id'), 'activities', ['user_id'], unique=False)
    op.create_index(op.f('ix_coach_memory_user_id'), 'coach_memory', ['user_id'], unique=False)
    op.create_index(op.f('ix_strava_tokens_athlete_id'), 'strava_tokens', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_strava_tokens_user_id'), 'strava_tokens', ['user_id'], unique=False)

    # Constraint
    op.create_unique_constraint(None, 'activity_analytics', ['activity_id'])

    # ⚠️ OPTIONAL (SAFE: comment for now)
    # op.alter_column('users', 'dob',
    #                existing_type=sa.VARCHAR(),
    #                type_=sa.DateTime(),
    #                existing_nullable=True)

    # ⚠️ OPTIONAL (only if sure)
    # op.drop_column('users', 'whatsapp_phone')


def downgrade() -> None:
    op.drop_index(op.f('ix_strava_tokens_user_id'), table_name='strava_tokens')
    op.drop_index(op.f('ix_strava_tokens_athlete_id'), table_name='strava_tokens')
    op.drop_index(op.f('ix_coach_memory_user_id'), table_name='coach_memory')
    op.drop_index(op.f('ix_activities_user_id'), table_name='activities')

    op.drop_constraint(None, 'activity_analytics', type_='unique')

    op.drop_column('activity_analytics', 'created_at')
    op.drop_column('activities', 'created_at')

    # Optional rollback
    # op.add_column('users', sa.Column('whatsapp_phone', sa.VARCHAR(), nullable=True))
    # op.alter_column('users', 'dob',
    #                existing_type=sa.DateTime(),
    #                type_=sa.VARCHAR(),
    #                existing_nullable=True)
