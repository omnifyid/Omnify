"""add_is_open_to_stores

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '8b9c0d1e2f3a'
down_revision: Union[str, Sequence[str], None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('is_open', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('stores', 'is_open')
