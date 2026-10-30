import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ShiftStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"  # counted, awaiting manager review
    REVIEWED = "REVIEWED"


class CashMovementType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"


class Shift(Base, TimestampMixin):
    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opened_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opening_cash: Mapped[int] = mapped_column(Integer, nullable=False)
    # cash on hand the system expected when the shift opened; opening_cash - this = gap between shifts
    carry_expected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    counted_cash: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_cash: Mapped[int | None] = mapped_column(Integer, nullable=True)  # snapshot at close
    variance: Mapped[int | None] = mapped_column(Integer, nullable=True)  # counted - expected
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default=ShiftStatus.OPEN.value, nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(String(300), nullable=True)


class CashMovement(Base, TimestampMixin):
    __tablename__ = "cash_movements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True
    )
