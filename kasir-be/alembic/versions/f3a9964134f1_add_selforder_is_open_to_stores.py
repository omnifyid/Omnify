"""add_selforder_is_open_to_stores

Revision ID: f3a9964134f1
Revises: f3a4b5c6d7e8
Create Date: 2026-05-28 10:48:40.487929

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a9964134f1'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'stores',
        sa.Column('selforder_is_open', sa.Boolean(), nullable=False, server_default='true'),
    )


def downgrade() -> None:
    op.drop_column('stores', 'selforder_is_open')
