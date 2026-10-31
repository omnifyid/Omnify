"""add businesses (shared catalog) and per-branch item settings

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
"""
import sqlalchemy as sa
from alembic import op

revision = "5e6f7a8b9c0d"
down_revision = "4d5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    # each existing store becomes its own business, reusing the store id
    op.execute("INSERT INTO businesses (id, name) SELECT id, name FROM stores")

    op.add_column("stores", sa.Column("business_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE stores SET business_id = id")
    op.alter_column("stores", "business_id", nullable=False)
    op.create_index("ix_stores_business_id", "stores", ["business_id"])
    op.create_foreign_key("fk_stores_business", "stores", "businesses", ["business_id"], ["id"], ondelete="RESTRICT")

    for table in ("items", "item_categories"):
        op.add_column(table, sa.Column("business_id", sa.Uuid(), nullable=True))
        op.execute(f"UPDATE {table} SET business_id = store_id")
        op.alter_column(table, "business_id", nullable=False)
        op.create_index(f"ix_{table}_business_id", table, ["business_id"])
        op.create_foreign_key(f"fk_{table}_business", table, "businesses", ["business_id"], ["id"], ondelete="CASCADE")

    op.create_table(
        "item_store_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_sold", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("item_id", "store_id", name="uq_item_store_setting"),
    )
    op.create_index("ix_item_store_settings_item_id", "item_store_settings", ["item_id"])
    op.create_index("ix_item_store_settings_store_id", "item_store_settings", ["store_id"])


def downgrade() -> None:
    op.drop_table("item_store_settings")
    for table in ("items", "item_categories"):
        op.drop_constraint(f"fk_{table}_business", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_business_id", table_name=table)
        op.drop_column(table, "business_id")
    op.drop_constraint("fk_stores_business", "stores", type_="foreignkey")
    op.drop_index("ix_stores_business_id", table_name="stores")
    op.drop_column("stores", "business_id")
    op.drop_table("businesses")
