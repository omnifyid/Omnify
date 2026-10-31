"""add extra_price to option_choices

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f9
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a8'
down_revision = 'a1b2c3d4e5f9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('option_choices', sa.Column('extra_price', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('option_choices', 'extra_price')
