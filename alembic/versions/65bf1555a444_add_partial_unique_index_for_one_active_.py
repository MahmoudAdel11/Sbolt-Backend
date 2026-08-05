"""add partial unique index for one active ride per rider

Revision ID: 65bf1555a444
Revises: b5b1093a02e6
Create Date: 2026-08-05 03:32:27.451719

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '65bf1555a444'
down_revision: str | None = 'b5b1093a02e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        'uq_rides_one_active_per_rider',
        'rides',
        ['rider_id'],
        unique=True,
        postgresql_where="status NOT IN ('completed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_index(
        'uq_rides_one_active_per_rider',
        table_name='rides',
        postgresql_where="status NOT IN ('completed', 'cancelled')",
    )
