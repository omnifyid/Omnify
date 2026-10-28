"""fix percentage discount values: convert plain % to basis points

Existing PERCENTAGE discounts were stored as plain percentages (e.g. 20 for 20%).
The calculation uses basis points (1000 = 10%), so 20% must be stored as 2000.

Revision ID: e1f2a3b4c5d6
Revises: d5e6f7a8b9c0
Create Date: 2026-05-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE discounts SET value = value * 100 WHERE discount_type = 'PERCENTAGE'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE discounts SET value = value / 100 WHERE discount_type = 'PERCENTAGE'"
    )
