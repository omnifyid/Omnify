"""add_item_channel_prices

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-10-29 19:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'item_channel_prices',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('item_id', sa.Uuid(), sa.ForeignKey('items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.UniqueConstraint('item_id', 'channel', name='uq_item_channel_price'),
    )
    op.create_index('ix_item_channel_prices_item_id', 'item_channel_prices', ['item_id'])


def downgrade() -> None:
    op.drop_table('item_channel_prices')
