"""add_category_icon

Revision ID: 7f3d8a2c1b90
Revises: 215de5d32fc4
Create Date: 2026-05-05 21:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "7f3d8a2c1b90"
down_revision: str | Sequence[str] | None = "215de5d32fc4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE item_categories ADD COLUMN icon VARCHAR(16)")


def downgrade() -> None:
    op.execute("ALTER TABLE item_categories DROP COLUMN icon")
