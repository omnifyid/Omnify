"""add_item_icon

Revision ID: a1b2c3d4e5f6
Revises: fd0832bc1574
Create Date: 2026-05-23 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "fd0832bc1574"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("icon", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "icon")
