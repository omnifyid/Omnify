"""store address/phone/receipt options and order cash received

Revision ID: 7a8b9c0d1e2f
Revises: 6f7a8b9c0d1e
"""
import sqlalchemy as sa
from alembic import op

revision = "7a8b9c0d1e2f"
down_revision = "6f7a8b9c0d1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("phone", sa.String(30), nullable=True))
    op.add_column("stores", sa.Column("receipt_options", sa.JSON(), nullable=True))
    op.add_column("orders", sa.Column("cash_received", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "cash_received")
    op.drop_column("stores", "receipt_options")
    op.drop_column("stores", "phone")
    op.drop_column("stores", "address")
