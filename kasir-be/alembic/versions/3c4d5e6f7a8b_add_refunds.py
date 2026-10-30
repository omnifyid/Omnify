"""add_refunds

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-10-30 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '3c4d5e6f7a8b'
down_revision: Union[str, Sequence[str], None] = '2b3c4d5e6f7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'order_refunds',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('order_id', sa.Uuid(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('store_id', sa.Uuid(), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('type', sa.String(10), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(200), nullable=False),
        sa.Column('order_item_id', sa.Uuid(), sa.ForeignKey('order_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_order_refunds_order_id', 'order_refunds', ['order_id'])
    op.create_index('ix_order_refunds_store_id', 'order_refunds', ['store_id'])
    op.create_index('ix_order_refunds_refunded_at', 'order_refunds', ['refunded_at'])
    op.add_column('orders', sa.Column('refunded_amount', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('driver_name', sa.String(100), nullable=True))
    op.add_column('order_items', sa.Column('void_qty', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('order_items', 'void_qty')
    op.drop_column('orders', 'driver_name')
    op.drop_column('orders', 'refunded_amount')
    op.drop_table('order_refunds')
