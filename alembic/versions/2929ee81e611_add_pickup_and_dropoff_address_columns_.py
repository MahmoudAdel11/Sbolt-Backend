"""add pickup and dropoff address columns to rides

Revision ID: 2929ee81e611
Revises: 926d20760240
Create Date: 2026-08-27 14:20:18.681193

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2929ee81e611'
down_revision: str | None = '926d20760240'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('rides', sa.Column('pickup_address', sa.String(), nullable=True))
    op.add_column('rides', sa.Column('dropoff_address', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('rides', 'dropoff_address')
    op.drop_column('rides', 'pickup_address')
