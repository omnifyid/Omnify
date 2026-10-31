"""add is_default to addon_choices

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b9'
down_revision = 'b2c3d4e5f6a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('addon_choices', sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('addon_choices', 'is_default')
