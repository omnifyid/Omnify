"""add_kitchen_management

Revision ID: a7b8c9d0e1f2
Revises: c4d5e6f7a8b9
Create Date: 2026-10-29 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

kitchen_status = postgresql.ENUM('NEW', 'COOKING', 'READY', 'SERVED', name='kitchen_status', create_type=False)


def upgrade() -> None:
    kitchen_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'stores',
        sa.Column('kitchen_enabled', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column('orders', sa.Column('kitchen_status', kitchen_status, nullable=True))
    op.create_index('ix_orders_kitchen_status', 'orders', ['kitchen_status'])
    op.add_column(
        'order_items',
        sa.Column('is_done', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('order_items', 'is_done')
    op.drop_index('ix_orders_kitchen_status', table_name='orders')
    op.drop_column('orders', 'kitchen_status')
    op.drop_column('stores', 'kitchen_enabled')
    kitchen_status.drop(op.get_bind(), checkfirst=True)
