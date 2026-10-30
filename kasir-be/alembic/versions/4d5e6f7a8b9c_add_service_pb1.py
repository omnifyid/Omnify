"""add_service_pb1

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-10-30 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '4d5e6f7a8b9c'
down_revision: Union[str, Sequence[str], None] = '3c4d5e6f7a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('service_bp', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('stores', sa.Column('pb1_bp', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('service_amount', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('pb1_amount', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('orders', 'pb1_amount')
    op.drop_column('orders', 'service_amount')
    op.drop_column('stores', 'pb1_bp')
    op.drop_column('stores', 'service_bp')
