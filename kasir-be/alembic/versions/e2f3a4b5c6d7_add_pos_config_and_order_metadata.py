"""add_pos_config_and_order_metadata

Revision ID: e2f3a4b5c6d7
Revises: f3a9964134f1
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'f3a9964134f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('pos_dine_in_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('stores', sa.Column('pos_table_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('stores', sa.Column('pos_table_count', sa.Integer(), nullable=False, server_default='10'))
    op.add_column('stores', sa.Column('pos_customer_name_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('orders', sa.Column('order_type', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('table_number', sa.String(50), nullable=True))
    op.add_column('orders', sa.Column('customer_name', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('stores', 'pos_dine_in_enabled')
    op.drop_column('stores', 'pos_table_enabled')
    op.drop_column('stores', 'pos_table_count')
    op.drop_column('stores', 'pos_customer_name_enabled')
    op.drop_column('orders', 'order_type')
    op.drop_column('orders', 'table_number')
    op.drop_column('orders', 'customer_name')
