"""add_shifts

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-10-30 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '2b3c4d5e6f7a'
down_revision: Union[str, Sequence[str], None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts():
    return [
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        'shifts',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('store_id', sa.Uuid(), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('opened_by', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('opening_cash', sa.Integer(), nullable=False),
        sa.Column('carry_expected', sa.Integer(), nullable=True),
        sa.Column('closed_by', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('counted_cash', sa.Integer(), nullable=True),
        sa.Column('expected_cash', sa.Integer(), nullable=True),
        sa.Column('variance', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(300), nullable=True),
        sa.Column('status', sa.String(10), nullable=False, server_default='OPEN'),
        sa.Column('reviewed_by', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('review_note', sa.String(300), nullable=True),
        *_ts(),
    )
    op.create_index('ix_shifts_store_id', 'shifts', ['store_id'])
    # at most one open shift per store
    op.create_index(
        'uq_shifts_one_open', 'shifts', ['store_id'], unique=True, postgresql_where=sa.text("status = 'OPEN'")
    )

    op.create_table(
        'cash_movements',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('shift_id', sa.Uuid(), sa.ForeignKey('shifts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('type', sa.String(3), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('reason', sa.String(200), nullable=False),
        sa.Column('expense_id', sa.Uuid(), sa.ForeignKey('expenses.id', ondelete='SET NULL'), nullable=True),
        *_ts(),
    )
    op.create_index('ix_cash_movements_shift_id', 'cash_movements', ['shift_id'])

    op.add_column('orders', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE orders SET confirmed_at = created_at WHERE status IN ('CONFIRMED', 'COMPLETED')"
    )
    op.add_column('stores', sa.Column('shift_variance_threshold', sa.Integer(), nullable=False, server_default='20000'))
    op.add_column('stores', sa.Column('default_float', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('stores', 'default_float')
    op.drop_column('stores', 'shift_variance_threshold')
    op.drop_column('orders', 'confirmed_at')
    op.drop_table('cash_movements')
    op.drop_table('shifts')
