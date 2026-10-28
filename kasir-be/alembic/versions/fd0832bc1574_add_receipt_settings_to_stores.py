"""add_receipt_settings_to_stores

Revision ID: fd0832bc1574
Revises: e1f2a3b4c5d6
Create Date: 2026-05-19 14:28:02.810248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'fd0832bc1574'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('show_logo', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('stores', sa.Column('receipt_header', sa.Text(), nullable=True))
    op.add_column('stores', sa.Column('receipt_footer', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('stores', 'receipt_footer')
    op.drop_column('stores', 'receipt_header')
    op.drop_column('stores', 'show_logo')
