"""add is_online column to users

Revision ID: a1c4e9f2b3d7
Revises: 8218e4e07c1e
Create Date: 2026-08-08 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c4e9f2b3d7'
down_revision: str | None = '8218e4e07c1e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_online', sa.Boolean(), server_default='false', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_online')
