"""add cost_price (HPP) to items

Revision ID: c4d5e6f7a8b9
Revises: ec9d1b20f1f8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'ec9d1b20f1f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('items', sa.Column('cost_price', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('items', 'cost_price')
