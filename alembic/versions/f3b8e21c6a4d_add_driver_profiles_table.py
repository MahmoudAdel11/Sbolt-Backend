"""add driver_profiles table, drop role/is_online from users

Revision ID: f3b8e21c6a4d
Revises: a1c4e9f2b3d7
Create Date: 2026-08-19 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3b8e21c6a4d'
down_revision: str | None = 'a1c4e9f2b3d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'driver_profiles',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('is_online', sa.Boolean(), server_default='false', nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_driver_profiles_user_id'),
    )

    # Backfill: every existing role='driver' user gets a driver_profiles row,
    # preserving their current is_online value rather than resetting it.
    op.execute(
        "INSERT INTO driver_profiles (user_id, is_online, created_at, updated_at) "
        "SELECT id, is_online, now(), now() FROM users WHERE role = 'driver'"
    )

    op.drop_column('users', 'is_online')
    op.drop_column('users', 'role')
    sa.Enum(name='user_role').drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    user_role = sa.Enum('rider', 'driver', name='user_role')
    user_role.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'users',
        sa.Column('role', user_role, server_default='rider', nullable=False),
    )
    op.add_column(
        'users',
        sa.Column('is_online', sa.Boolean(), server_default='false', nullable=False),
    )

    # Reverse the backfill: any user with a driver_profiles row becomes role='driver'
    # again, with their is_online value carried back onto users.
    op.execute(
        "UPDATE users SET role = 'driver', is_online = driver_profiles.is_online "
        "FROM driver_profiles WHERE users.id = driver_profiles.user_id"
    )

    op.drop_table('driver_profiles')
