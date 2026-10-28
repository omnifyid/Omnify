"""add name to discounts, make code nullable

Revision ID: b1c2d3e4f5a6
Revises: a064cf684c8e
Create Date: 2026-05-17 14:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a064cf684c8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('discounts', sa.Column('name', sa.String(100), nullable=False, server_default=''))
    op.alter_column('discounts', 'code', existing_type=sa.String(50), nullable=True)


def downgrade() -> None:
    op.alter_column('discounts', 'code', existing_type=sa.String(50), nullable=False)
    op.drop_column('discounts', 'name')
