"""add inventory and finance module flags to stores

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
"""
import sqlalchemy as sa
from alembic import op

revision = "6f7a8b9c0d1e"
down_revision = "5e6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ("inventory_enabled", "finance_enabled"):
        op.add_column("stores", sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    for col in ("finance_enabled", "inventory_enabled"):
        op.drop_column("stores", col)
