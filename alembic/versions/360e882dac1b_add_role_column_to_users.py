"""add role column to users

Revision ID: 360e882dac1b
Revises: 323087309716
Create Date: 2026-08-03 22:05:18.782218

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '360e882dac1b'
down_revision: str | None = '323087309716'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_role = sa.Enum('rider', 'driver', name='user_role')
    user_role.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'users',
        sa.Column('role', user_role, server_default='rider', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('users', 'role')
    sa.Enum(name='user_role').drop(op.get_bind(), checkfirst=True)
