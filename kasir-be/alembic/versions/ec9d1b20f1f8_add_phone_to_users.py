"""add_phone_to_users

Revision ID: ec9d1b20f1f8
Revises: a9b8c7d6e5f4
Create Date: 2026-05-29 20:22:29.991709

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'ec9d1b20f1f8'
down_revision: Union[str, Sequence[str], None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_phone'), table_name='users')
    op.drop_column('users', 'phone')
