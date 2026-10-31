"""add guest_count, segment to orders and note to order_items

Revision ID: a1b2c3d4e5f9
Revises: 0d1e2f3a4b5c
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f9'
down_revision = '0d1e2f3a4b5c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('guest_count', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('segment', sa.String(40), nullable=True))
    op.add_column('order_items', sa.Column('note', sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column('order_items', 'note')
    op.drop_column('orders', 'segment')
    op.drop_column('orders', 'guest_count')
