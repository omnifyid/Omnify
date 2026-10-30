"""add_online_channels

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-29 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'PLATFORM'")

    op.add_column('stores', sa.Column('tax_bp', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('channel', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('channel_order_id', sa.String(50), nullable=True))
    op.add_column('orders', sa.Column('app_total', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('commission_amount', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('expected_payout', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('tax_amount', sa.Integer(), nullable=True))
    op.create_index('ix_orders_channel', 'orders', ['channel'])

    op.create_table(
        'channel_settings',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('store_id', sa.Uuid(), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('commission_bp', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('markup_bp', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('store_id', 'channel', name='uq_channel_store'),
    )
    op.create_index('ix_channel_settings_store_id', 'channel_settings', ['store_id'])


def downgrade() -> None:
    op.drop_table('channel_settings')
    op.drop_index('ix_orders_channel', table_name='orders')
    for col in ('tax_amount', 'expected_payout', 'commission_amount', 'app_total', 'channel_order_id', 'channel'):
        op.drop_column('orders', col)
    op.drop_column('stores', 'tax_bp')
    # enum value 'PLATFORM' cannot be dropped from a Postgres enum
