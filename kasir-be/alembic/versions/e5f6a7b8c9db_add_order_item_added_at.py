"""add added_at to order_items (lines added to an open bill)

Revision ID: e5f6a7b8c9db
Revises: d4e5f6a7b8ca
"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9db'
down_revision = 'd4e5f6a7b8ca'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('order_items', sa.Column('added_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('order_items', 'added_at')
