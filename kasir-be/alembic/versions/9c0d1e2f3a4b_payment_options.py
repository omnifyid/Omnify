"""payment_options on stores, payment_provider on orders

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '9c0d1e2f3a4b'
down_revision: Union[str, Sequence[str], None] = '8b9c0d1e2f3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('payment_options', sa.JSON(), nullable=True))
    op.add_column('orders', sa.Column('payment_provider', sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'payment_provider')
    op.drop_column('stores', 'payment_options')
