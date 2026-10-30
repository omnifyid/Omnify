"""add_finance

Revision ID: 1a2b3c4d5e6f
Revises: d0e1f2a3b4c5
Create Date: 2026-10-30 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TS = lambda: [  # noqa: E731
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
]


def upgrade() -> None:
    op.create_table(
        'expenses',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('store_id', sa.Uuid(), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('description', sa.String(200), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('recurring', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('status', sa.String(10), nullable=False, server_default='POSTED'),
        *TS(),
    )
    op.create_index('ix_expenses_store_id', 'expenses', ['store_id'])
    op.create_index('ix_expenses_date', 'expenses', ['date'])

    op.create_table(
        'platform_settlements',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('store_id', sa.Uuid(), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('received_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('expected', sa.Integer(), nullable=False),
        sa.Column('diff', sa.Integer(), nullable=False),
        sa.Column('order_count', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(200), nullable=True),
        *TS(),
    )
    op.create_index('ix_platform_settlements_store_id', 'platform_settlements', ['store_id'])
    op.create_index('ix_platform_settlements_channel', 'platform_settlements', ['channel'])

    op.add_column('orders', sa.Column('expected_payout_date', sa.Date(), nullable=True))
    op.add_column(
        'orders',
        sa.Column('settlement_id', sa.Uuid(), sa.ForeignKey('platform_settlements.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_orders_settlement_id', 'orders', ['settlement_id'])
    op.add_column(
        'channel_settings',
        sa.Column('payout_lag_days', sa.Integer(), nullable=False, server_default='2'),
    )
    op.execute(
        "UPDATE orders SET expected_payout_date = (created_at::date + 2) WHERE channel IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column('channel_settings', 'payout_lag_days')
    op.drop_index('ix_orders_settlement_id', table_name='orders')
    op.drop_column('orders', 'settlement_id')
    op.drop_column('orders', 'expected_payout_date')
    op.drop_table('platform_settlements')
    op.drop_table('expenses')
