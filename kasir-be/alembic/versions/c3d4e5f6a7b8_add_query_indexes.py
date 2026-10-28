"""add_query_indexes

Revision ID: c3d4e5f6a7b8
Revises: 7f3d8a2c1b90
Create Date: 2026-05-13 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "7f3d8a2c1b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # FK indexes on order_items (missing, needed for order detail joins)
    op.create_index("ix_order_items_item_id", "order_items", ["item_id"])
    op.create_index("ix_order_items_package_id", "order_items", ["package_id"])

    # FK index on package_items
    op.create_index("ix_package_items_item_id", "package_items", ["item_id"])

    # FK index on orders.discount_id
    op.create_index("ix_orders_discount_id", "orders", ["discount_id"])

    # Composite indexes used by dashboard and report queries
    op.create_index("ix_orders_store_status", "orders", ["store_id", "status"])
    op.create_index("ix_orders_store_created_at", "orders", ["store_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_orders_store_created_at", table_name="orders")
    op.drop_index("ix_orders_store_status", table_name="orders")
    op.drop_index("ix_orders_discount_id", table_name="orders")
    op.drop_index("ix_package_items_item_id", table_name="package_items")
    op.drop_index("ix_order_items_package_id", table_name="order_items")
    op.drop_index("ix_order_items_item_id", table_name="order_items")
