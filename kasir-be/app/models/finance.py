import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ExpenseSource(str, enum.Enum):
    BANK = "BANK"
    EWALLET = "EWALLET"
    PETTY = "PETTY"
    DRAWER = "DRAWER"  # cash from the register; requires an open shift


class ExpenseStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"


# Expense categories; a drawer cash-out in one of these also becomes an expense
EXPENSE_CATEGORIES = [
    "Sewa", "Listrik & air", "Gaji & upah", "Bahan non-stok", "Marketing",
    "Perbaikan & perawatan", "Transport", "Internet & software", "Lain-lain",
]


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default=ExpenseStatus.POSTED.value, nullable=False)


class PlatformSettlement(Base, TimestampMixin):
    """Money received from an online platform, covering a set of its orders."""

    __tablename__ = "platform_settlements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    expected: Mapped[int] = mapped_column(Integer, nullable=False)
    diff: Mapped[int] = mapped_column(Integer, nullable=False)  # amount - expected
    order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
