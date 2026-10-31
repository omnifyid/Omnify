"""add OPEN to order_status (open bill)

Revision ID: d4e5f6a7b8ca
Revises: c3d4e5f6a7b9
"""
from alembic import op

revision = 'd4e5f6a7b8ca'
down_revision = 'c3d4e5f6a7b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'OPEN'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value; unpaid bills are turned into cancelled orders instead
    op.execute("UPDATE orders SET status = 'CANCELLED' WHERE status = 'OPEN'")
