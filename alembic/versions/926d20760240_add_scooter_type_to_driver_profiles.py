"""add scooter_type to driver_profiles

Revision ID: 926d20760240
Revises: e2f743f14ebc
Create Date: 2026-08-26 22:48:14.570375

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '926d20760240'
down_revision: str | None = 'e2f743f14ebc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'driver_profiles',
        sa.Column(
            'scooter_type', sa.Enum('economy', 'comfort', 'premium', name='ride_tier'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('driver_profiles', 'scooter_type')
