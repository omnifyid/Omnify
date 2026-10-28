"""add item discounts and max cap

Revision ID: a064cf684c8e
Revises: d5e6f7a8b9c0
Create Date: 2026-05-17 13:48:25.177344

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a064cf684c8e'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE discount_scope AS ENUM ('ORDER', 'ITEM')")
    op.execute("CREATE TYPE discount_target AS ENUM ('ALL', 'CATEGORY', 'ITEM')")
    op.add_column('discounts', sa.Column('max_discount_amount', sa.Integer(), nullable=True))
    op.add_column('discounts', sa.Column(
        'scope',
        sa.Enum('ORDER', 'ITEM', name='discount_scope'),
        server_default='ORDER',
        nullable=False,
    ))
    op.add_column('discounts', sa.Column(
        'target_type',
        sa.Enum('ALL', 'CATEGORY', 'ITEM', name='discount_target'),
        nullable=True,
    ))
    op.add_column('discounts', sa.Column('target_item_id', sa.Uuid(), nullable=True))
    op.add_column('discounts', sa.Column('target_category_id', sa.Uuid(), nullable=True))
    op.add_column('discounts', sa.Column(
        'is_automatic', sa.Boolean(), server_default='false', nullable=False
    ))
    op.create_foreign_key(
        'fk_discounts_target_item_id', 'discounts', 'items',
        ['target_item_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_discounts_target_category_id', 'discounts', 'item_categories',
        ['target_category_id'], ['id'], ondelete='SET NULL',
    )
    op.add_column('order_items', sa.Column(
        'item_discount_amount', sa.Integer(), server_default='0', nullable=False
    ))


def downgrade() -> None:
    op.drop_column('order_items', 'item_discount_amount')
    op.drop_constraint('fk_discounts_target_category_id', 'discounts', type_='foreignkey')
    op.drop_constraint('fk_discounts_target_item_id', 'discounts', type_='foreignkey')
    op.drop_column('discounts', 'is_automatic')
    op.drop_column('discounts', 'target_category_id')
    op.drop_column('discounts', 'target_item_id')
    op.drop_column('discounts', 'target_type')
    op.drop_column('discounts', 'scope')
    op.drop_column('discounts', 'max_discount_amount')
    op.execute("DROP TYPE IF EXISTS discount_scope")
    op.execute("DROP TYPE IF EXISTS discount_target")
