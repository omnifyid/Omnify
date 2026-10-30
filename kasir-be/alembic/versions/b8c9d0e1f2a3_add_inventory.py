"""add_inventory

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-29 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ingredients',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('store_id', sa.Uuid(), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('stock', sa.Numeric(14, 3), nullable=False, server_default='0'),
        sa.Column('min_stock', sa.Numeric(14, 3), nullable=False, server_default='0'),
        sa.Column('cost_price', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('store_id', 'name', name='uq_ingredient_store_name'),
    )
    op.create_index('ix_ingredients_store_id', 'ingredients', ['store_id'])

    op.create_table(
        'recipe_lines',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('item_id', sa.Uuid(), sa.ForeignKey('items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', sa.Uuid(), sa.ForeignKey('ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
        sa.UniqueConstraint('item_id', 'ingredient_id', name='uq_recipe_item_ingredient'),
    )
    op.create_index('ix_recipe_lines_item_id', 'recipe_lines', ['item_id'])
    op.create_index('ix_recipe_lines_ingredient_id', 'recipe_lines', ['ingredient_id'])

    op.create_table(
        'stock_movements',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('store_id', sa.Uuid(), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', sa.Uuid(), sa.ForeignKey('ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('order_id', sa.Uuid(), sa.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('type', sa.String(16), nullable=False),
        sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
        sa.Column('balance_after', sa.Numeric(14, 3), nullable=False),
        sa.Column('note', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_stock_movements_store_id', 'stock_movements', ['store_id'])
    op.create_index('ix_stock_movements_ingredient_id', 'stock_movements', ['ingredient_id'])
    op.create_index('ix_stock_movements_order_id', 'stock_movements', ['order_id'])


def downgrade() -> None:
    op.drop_table('stock_movements')
    op.drop_table('recipe_lines')
    op.drop_table('ingredients')
